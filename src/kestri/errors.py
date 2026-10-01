"""Safe failure categories; never attach provider bodies or credentials."""


class PolicyDenied(Exception):
    pass


class BudgetExceeded(Exception):
    pass


class ContextExceeded(Exception):
    pass


class ProviderFailure(Exception):
    pass
