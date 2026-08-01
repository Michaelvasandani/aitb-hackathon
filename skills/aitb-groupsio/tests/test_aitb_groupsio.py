"""Tests for aitb-groupsio.py — Groups.io mailing list draft creation."""

import os
from unittest.mock import MagicMock, patch

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "aitb_groupsio",
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "scripts",
        "aitb-groupsio.py",
    ),
)
aitb_groupsio = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(aitb_groupsio)


class TestSendEmail:
    """send_email() calls the approved Gmail draft wrapper."""

    @patch("subprocess.run")
    def test_constructs_draft_command(self, mock_run):
        # Arrange
        mock_run.return_value = MagicMock(returncode=0, stdout="sent", stderr="")

        # Act
        success, result = aitb_groupsio.send_email(
            "test@groups.io", "Hello", "Message body"
        )

        # Assert
        assert success is True
        args = mock_run.call_args
        cmd = args[0][0]
        assert cmd[:2] == ["python3", aitb_groupsio.DRAFT_EMAIL_SCRIPT]
        assert "--account" in cmd
        assert "aitb" in cmd
        assert "--to" in cmd
        assert "test@groups.io" in cmd
        assert "--subject" in cmd
        assert "--body-stdin" in cmd
        assert "--no-signature" in cmd
        assert "--not-sales" in cmd

    @patch("subprocess.run")
    def test_body_passed_via_stdin(self, mock_run):
        # Arrange
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        # Act
        aitb_groupsio.send_email("test@groups.io", "Subj", "Body text")

        # Assert
        assert mock_run.call_args.kwargs.get("input") == "Body text"

    @patch("subprocess.run")
    def test_failure_returns_false(self, mock_run):
        # Arrange
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="auth failed")

        # Act
        success, result = aitb_groupsio.send_email("test@groups.io", "Subj", "Body")

        # Assert
        assert success is False
        assert "auth failed" in result

    @patch("subprocess.run")
    def test_cc_included_when_provided(self, mock_run):
        # Arrange
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        # Act
        aitb_groupsio.send_email("test@groups.io", "Subj", "Body", cc="cc@example.com")

        # Assert
        cmd = mock_run.call_args[0][0]
        assert "--cc" in cmd
        assert "cc@example.com" in cmd


class TestPost:
    """post() drafts to the mailing list with optional signature."""

    @patch("subprocess.run")
    def test_appends_default_signature(self, mock_run, capsys):
        # Arrange
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        # Act
        aitb_groupsio.post("Test Subject", "Test body")

        # Assert
        body_sent = mock_run.call_args.kwargs.get("input", "")
        assert "AI Trailblazers" in body_sent

    @patch("subprocess.run")
    def test_appends_named_signature(self, mock_run, capsys):
        # Arrange
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        # Act
        aitb_groupsio.post("Subject", "Body", from_name="Aaron Eden")

        # Assert
        body_sent = mock_run.call_args.kwargs.get("input", "")
        assert "Aaron Eden" in body_sent
        assert "AI Trailblazers" in body_sent

    @patch("subprocess.run")
    def test_sends_to_group_email(self, mock_run, capsys):
        # Arrange
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        # Act
        aitb_groupsio.post("Subject", "Body")

        # Assert
        cmd = mock_run.call_args[0][0]
        assert "ai-trailblazers@groups.io" in cmd
