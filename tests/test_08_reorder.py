def test_reorder(ctestdir):
    test_a = """
        import pytest

        @pytest.mark.dependency(
            depends=['test_b']
        )
        def test_a():
            pass

        @pytest.mark.dependency(
            depends=['test_c']
        )
        def test_b():
            pass

        @pytest.mark.dependency()
        def test_c():
            pass
    """
    ctestdir.makepyfile(test_a=test_a)

    result = ctestdir.runpytest("--verbose")
    result.assert_outcomes(passed=3)
    result.stdout.fnmatch_lines("""
        *::test_c PASSED
        *::test_b PASSED
        *::test_a PASSED
    """)


def test_unknown(ctestdir):
    test_a = """
        import pytest

        @pytest.mark.dependency(
            depends=['test_b']
        )
        def test_a():
            pass

        @pytest.mark.dependency(
            depends=['test_c']
        )
        def test_b():
            pass
    """
    ctestdir.makepyfile(test_a=test_a)

    result = ctestdir.runpytest("--verbose")
    result.assert_outcomes(skipped=2)
    result.stderr.fnmatch_lines("""
        test_b has unknown dependencies
    """)
    result.stdout.fnmatch_lines("""
        *::test_b SKIPPED
        *::test_a SKIPPED
    """)


def test_circular(ctestdir):
    test_a = """
        import pytest

        @pytest.mark.dependency(
            depends=['test_b']
        )
        def test_a():
            pass

        @pytest.mark.dependency(
            depends=['test_a']
        )
        def test_b():
            pass
    """
    ctestdir.makepyfile(test_a=test_a)

    result = ctestdir.runpytest("--verbose")
    result.assert_outcomes(skipped=2)
    result.stderr.fnmatch_lines("""
        test_a has circular dependencies
    """)
    result.stdout.fnmatch_lines("""
        *::test_a SKIPPED
        *::test_b SKIPPED
    """)
