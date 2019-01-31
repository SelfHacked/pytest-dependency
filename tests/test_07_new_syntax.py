def test_new_syntax(ctestdir):
    test_a = """
        import pytest

        @pytest.mark.dependency()
        def test_a():
            pass

        class TestClass(object):
            @pytest.mark.dependency()
            def test_b(self):
                pass

            @pytest.mark.dependency(
                depends=[
                    ('module', 'test_a'),
                    ('class', 'test_b'),
                ]
            )
            def test_c(self):
                pass
    """
    ctestdir.makepyfile(test_a=test_a)

    result = ctestdir.runpytest("--verbose")
    result.assert_outcomes(passed=3)
    result.stdout.fnmatch_lines("""
        *::test_a PASSED
        *::TestClass::test_b PASSED
        *::TestClass::test_c PASSED
    """)
