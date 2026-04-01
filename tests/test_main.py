"""Tests for main module."""

from dziemian_mc_agent.main import main


def test_main(capsys):
    """Test main function."""
    main()
    captured = capsys.readouterr()
    assert "Hello from DziemianMCAgent!" in captured.out
