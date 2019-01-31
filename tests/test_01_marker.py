"""
The most basic test: check that the marker works.
"""


def test_marker_registered(ctestdir):
    result = ctestdir.runpytest("--markers")
    result.stdout.fnmatch_lines("""
        @pytest.mark.dependency*
    """)


def test_marker(ctestdir):
    ctestdir.makepyfile("""
        import pytest
        from pytest_dependency import DependencyFinder

        @pytest.mark.dependency()
        def test_marker(request):
            node = request.node.getparent(pytest.Module)
            assert hasattr(node, 'dependency_finder')
            assert isinstance(node.dependency_finder, DependencyFinder)
            assert 'test_marker' in node.dependency_finder
    """)
    result = ctestdir.runpytest("--verbose")
    result.assert_outcomes(passed=1)
