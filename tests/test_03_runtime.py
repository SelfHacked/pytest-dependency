"""
Using depends() to mark dependencies at runtime.
"""


def test_skip_depend_runtime(ctestdir):
    """One test is skipped, other dependent tests are skipped as well.
    This also includes indirect dependencies.
    """
    ctestdir.makepyfile("""
        import pytest
        from pytest_dependency import depends

        @pytest.mark.dependency()
        def test_a():
            pass

        @pytest.mark.dependency()
        def test_b():
            pytest.skip("explicit skip")

        @pytest.mark.dependency()
        def test_c(request):
            depends(request, ["test_b"])
            pass

        @pytest.mark.dependency()
        def test_d(request):
            depends(request, ["test_a", "test_c"])
            pass
    """)
    result = ctestdir.runpytest("--verbose")
    result.assert_outcomes(passed=1, skipped=3, failed=0)
    result.stdout.fnmatch_lines("""
        *::test_a PASSED
        *::test_b SKIPPED
        *::test_c SKIPPED
        *::test_d SKIPPED
    """)
