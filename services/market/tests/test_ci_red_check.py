"""Deliberately failing test, only on the throwaway ci-red-check branch: proves CI turns red."""


def test_ci_turns_red_on_a_failing_test():
    assert 1 + 1 == 3
