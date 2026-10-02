"""Low-priority automatic-memory extraction with persistent jobs and existing USD ledger."""

import asyncio

import httpx
from langchain_core.language_models import BaseChatModel
from openai import APIConnectionError, APIStatusError

from kestri.agent.budget import Budget, RunControl, micro_usd
from kestri.errors import BudgetExceeded, PolicyDenied
from kestri.memory.extractor import MemoryExtractor
from kestri.memory.repository import MemoryRepository
from kestri.settings import ResearchSettings
from kestri.storage.store import Row, Store


class MemoryJobControl(RunControl):
    def __init__(self, repository: MemoryRepository, job: Row) -> None:
        super().__init__(repository.store, job["run_id"])
        self.repository = repository
        self.job = job

    async def ensure_active(self) -> None:
        await self.repository.ensure_active(self.job)
        await super().ensure_active()


class MemoryBudget(Budget):
    async def reserve(self, kind: str, amount: int) -> str:
        await self.control.ensure_active()
        assert isinstance(self.control, MemoryJobControl)
        return await self.control.store.reserve(
            self.control.run_id,
            "memory_extract",
            amount,
            micro_usd(self.settings.monthly_budget_usd),
            micro_usd(self.settings.memory_maintenance_budget_usd),
            maintenance_monthly=micro_usd(self.settings.memory_maintenance_monthly_usd),
            maintenance_job=(str(self.control.job["id"]), str(self.control.job["lease_token"])),
        )


class MemoryWorker:
    def __init__(self, store: Store, settings: ResearchSettings, model: BaseChatModel) -> None:
        self.repository = MemoryRepository(store, settings)
        self.extractor = MemoryExtractor(model, store.redactor)
        # Independent cap, conservative output allowance and a deadline shorter than lease.
        self.settings = settings.model_copy(
            update={
                "run_timeout_seconds": min(settings.run_timeout_seconds, 60),
                "max_output_tokens": min(settings.max_output_tokens, 2048),
            }
        )

    async def work_once(self, chat_id: int) -> bool:
        job = await self.repository.claim(chat_id)
        if job is None:
            return False
        control = MemoryJobControl(self.repository, job)
        try:
            result = await self.extractor.extract(
                await self.repository.snapshot(job), MemoryBudget(self.settings, control)
            )
            await self.repository.publish(job, result)
        except asyncio.CancelledError:
            await self.repository.fail(job, "WorkerInterrupted", retry=True)
            raise
        except TimeoutError, httpx.HTTPError, APIConnectionError:
            await self.repository.fail(job, "ProviderTransient", retry=True)
        except APIStatusError as error:
            await self.repository.fail(
                job,
                "ProviderTransient"
                if error.status_code >= 500 or error.status_code == 429
                else "ProviderRejected",
                retry=error.status_code >= 500 or error.status_code == 429,
            )
        except PolicyDenied as error:
            # Only version conflicts are retryable. Policy messages contain fixed categories.
            await self.repository.fail(
                job,
                "MemoryJobChanged" if str(error) == "MemoryJobChanged" else "PolicyRejected",
                retry=str(error) == "MemoryJobChanged",
            )
        except BudgetExceeded:
            await self.repository.fail(job, "MaintenanceBudgetExceeded")
        except Exception:
            await self.repository.fail(job, "InvalidExtraction")
        return True
