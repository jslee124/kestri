"""Application-managed evidence only, opened relative to no-follow directory handles."""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID

from kestri.errors import PolicyDenied


class Workspace:
    def __init__(self, root: Path) -> None:
        if root.is_symlink():
            raise PolicyDenied("WorkspaceSymlink")
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.root = root.absolute()

    @contextmanager
    def directory(self, run_id: str, *, create: bool = True) -> Iterator[int]:
        try:
            safe_id = str(UUID(run_id))
            root_fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                if create:
                    try:
                        os.mkdir(safe_id, 0o700, dir_fd=root_fd)
                    except FileExistsError:
                        pass
                run_fd = os.open(
                    safe_id,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=root_fd,
                )
                try:
                    yield run_fd
                finally:
                    os.close(run_fd)
            finally:
                os.close(root_fd)
        except (OSError, ValueError) as error:
            raise PolicyDenied("WorkspaceBoundary") from error

    def write(self, run_id: str, evidence_id: str, content: str) -> None:
        filename = f"{UUID(evidence_id)}.txt"
        with self.directory(run_id) as directory:
            descriptor = os.open(
                filename,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=directory,
            )
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(content)

    def read(self, run_id: str, evidence_id: str, limit: int) -> tuple[str, bool]:
        filename = f"{UUID(evidence_id)}.txt"
        with self.directory(run_id, create=False) as directory:
            descriptor = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
            with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
                content = stream.read(limit + 1)
        return content[:limit], len(content) > limit

    def remove(self, run_id: str, evidence_id: str) -> None:
        """Remove one generated evidence file without following any directory links."""
        filename = f"{UUID(evidence_id)}.txt"
        try:
            with self.directory(run_id, create=False) as directory:
                try:
                    os.unlink(filename, dir_fd=directory)
                except FileNotFoundError:
                    pass
        except PolicyDenied as error:
            if isinstance(error.__cause__, FileNotFoundError):
                return
            raise

    def write_image(self, run_id: str, image_id: str, data: bytes) -> None:
        filename = f"{UUID(image_id)}.image"
        with self.directory(run_id) as directory:
            descriptor = os.open(
                filename,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=directory,
            )
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())

    def read_image(self, run_id: str, image_id: str, limit: int) -> bytes:
        import stat

        filename = f"{UUID(image_id)}.image"
        with self.directory(run_id, create=False) as directory:
            descriptor = os.open(
                filename, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
            )
            with os.fdopen(descriptor, "rb") as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
                    raise PolicyDenied("ImageFileBoundary")
                data = stream.read(limit + 1)
        if len(data) > limit:
            raise PolicyDenied("ImageSizeLimit")
        return data

    def remove_image(self, run_id: str, image_id: str) -> None:
        filename = f"{UUID(image_id)}.image"
        try:
            with self.directory(run_id, create=False) as directory:
                try:
                    os.unlink(filename, dir_fd=directory)
                except FileNotFoundError:
                    pass
        except PolicyDenied as error:
            if isinstance(error.__cause__, FileNotFoundError):
                return
            raise
