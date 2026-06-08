from dataclasses import dataclass


@dataclass
class MutBool:
    """A mutable wrapper for bool. Mutability allows for usage in recursive calls where parameters are also outputs."""

    value: bool = False
