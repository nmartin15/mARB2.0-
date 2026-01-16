"""Tests for enhanced memory monitoring utilities."""
from unittest.mock import patch

import pytest

from app.utils.memory_monitor import (
    MEMORY_CRITICAL_THRESHOLD_MB,
    MEMORY_DELTA_CRITICAL_MB,
    MEMORY_DELTA_WARNING_MB,
    MEMORY_WARNING_THRESHOLD_MB,
    SYSTEM_MEMORY_CRITICAL_PCT,
    SYSTEM_MEMORY_WARNING_PCT,
    MemoryStats,
    check_memory_thresholds,
    get_memory_stats,
    get_memory_usage,
    get_system_memory,
    log_memory_checkpoint,
)


class TestMemoryUsage:
    """Tests for get_memory_usage function."""

    def test_get_memory_usage_with_psutil(self):
        """Test memory usage retrieval when psutil is available."""
        memory = get_memory_usage()
        # Should return a positive number (or 0.0 if psutil fails)
        assert isinstance(memory, float)
        assert memory >= 0.0

    @patch("app.utils.memory_monitor.PSUTIL_AVAILABLE", False)
    def test_get_memory_usage_without_psutil(self):
        """Test memory usage when psutil is not available."""
        memory = get_memory_usage()
        assert memory == 0.0


class TestSystemMemory:
    """Tests for get_system_memory function."""

    def test_get_system_memory_with_psutil(self):
        """Test system memory retrieval when psutil is available."""
        total, available, percent = get_system_memory()
        # Should return values or None if unavailable
        if total is not None:
            assert isinstance(total, float)
            assert total > 0
        if available is not None:
            assert isinstance(available, float)
            assert available >= 0
        if percent is not None:
            assert isinstance(percent, float)
            assert 0 <= percent <= 100

    @patch("app.utils.memory_monitor.PSUTIL_AVAILABLE", False)
    def test_get_system_memory_without_psutil(self):
        """Test system memory when psutil is not available."""
        total, available, percent = get_system_memory()
        assert total is None
        assert available is None
        assert percent is None


class TestMemoryStats:
    """Tests for MemoryStats class."""

    def test_memory_stats_creation(self):
        """Test creating MemoryStats object."""
        stats = MemoryStats(
            process_memory_mb=100.0,
            process_memory_delta_mb=50.0,
            system_memory_total_mb=8192.0,
            system_memory_available_mb=4096.0,
            system_memory_percent=50.0,
            peak_memory_mb=150.0,
        )
        assert stats.process_memory_mb == pytest.approx(100.0)
        assert stats.process_memory_delta_mb == pytest.approx(50.0)
        assert stats.system_memory_total_mb == pytest.approx(8192.0)
        assert stats.system_memory_available_mb == pytest.approx(4096.0)
        assert stats.system_memory_percent == pytest.approx(50.0)
        assert stats.peak_memory_mb == pytest.approx(150.0)

    def test_memory_stats_to_dict(self):
        """Test converting MemoryStats to dictionary."""
        stats = MemoryStats(
            process_memory_mb=100.5,
            process_memory_delta_mb=50.25,
            system_memory_total_mb=8192.0,
            system_memory_available_mb=4096.0,
            system_memory_percent=50.0,
            peak_memory_mb=150.75,
        )
        stats_dict = stats.to_dict()
        assert isinstance(stats_dict, dict)
        assert stats_dict["process_memory_mb"] == pytest.approx(100.5)
        assert stats_dict["process_memory_delta_mb"] == pytest.approx(50.25)
        assert stats_dict["system_memory_percent"] == pytest.approx(50.0)
        assert stats_dict["peak_memory_mb"] == pytest.approx(150.75)


class TestGetMemoryStats:
    """Tests for get_memory_stats function."""

    def test_get_memory_stats(self):
        """Test getting comprehensive memory statistics."""
        stats = get_memory_stats(start_memory_mb=100.0, peak_memory_mb=150.0)
        assert isinstance(stats, MemoryStats)
        assert stats.process_memory_mb >= 0.0
        # Delta should be calculated from start_memory
        if stats.process_memory_mb > 0:
            assert isinstance(stats.process_memory_delta_mb, float)

    def test_get_memory_stats_without_start(self):
        """Test getting memory stats without start memory."""
        stats = get_memory_stats()
        assert isinstance(stats, MemoryStats)
        assert stats.process_memory_delta_mb == 0.0


class TestCheckMemoryThresholds:
    """Tests for check_memory_thresholds function."""

    def test_check_memory_thresholds_normal(self):
        """Test threshold checking with normal memory usage."""
        stats = MemoryStats(
            process_memory_mb=100.0,
            process_memory_delta_mb=50.0,
            system_memory_percent=50.0,
        )
        results = check_memory_thresholds(stats, "test_operation", "test_checkpoint")
        assert isinstance(results, dict)
        assert results["process_warning"] is False
        assert results["process_critical"] is False
        assert results["delta_warning"] is False
        assert results["delta_critical"] is False

    def test_check_memory_thresholds_process_warning(self):
        """Test threshold checking with process memory warning."""
        stats = MemoryStats(
            process_memory_mb=MEMORY_WARNING_THRESHOLD_MB + 10,
            process_memory_delta_mb=50.0,
            system_memory_percent=50.0,
        )
        results = check_memory_thresholds(stats, "test_operation", "test_checkpoint")
        assert results["process_warning"] is True
        assert results["process_critical"] is False

    def test_check_memory_thresholds_process_critical(self):
        """Test threshold checking with process memory critical."""
        stats = MemoryStats(
            process_memory_mb=MEMORY_CRITICAL_THRESHOLD_MB + 10,
            process_memory_delta_mb=50.0,
            system_memory_percent=50.0,
        )
        results = check_memory_thresholds(stats, "test_operation", "test_checkpoint")
        assert results["process_warning"] is True
        assert results["process_critical"] is True

    def test_check_memory_thresholds_delta_warning(self):
        """Test threshold checking with memory delta warning."""
        stats = MemoryStats(
            process_memory_mb=100.0,
            process_memory_delta_mb=MEMORY_DELTA_WARNING_MB + 10,
            system_memory_percent=50.0,
        )
        results = check_memory_thresholds(stats, "test_operation", "test_checkpoint")
        assert results["delta_warning"] is True
        assert results["delta_critical"] is False

    def test_check_memory_thresholds_delta_critical(self):
        """Test threshold checking with memory delta critical."""
        stats = MemoryStats(
            process_memory_mb=100.0,
            process_memory_delta_mb=MEMORY_DELTA_CRITICAL_MB + 10,
            system_memory_percent=50.0,
        )
        results = check_memory_thresholds(stats, "test_operation", "test_checkpoint")
        assert results["delta_warning"] is True
        assert results["delta_critical"] is True

    def test_check_memory_thresholds_system_warning(self):
        """Test threshold checking with system memory warning."""
        stats = MemoryStats(
            process_memory_mb=100.0,
            process_memory_delta_mb=50.0,
            system_memory_percent=SYSTEM_MEMORY_WARNING_PCT + 5,
        )
        results = check_memory_thresholds(stats, "test_operation", "test_checkpoint")
        assert results["system_warning"] is True
        assert results["system_critical"] is False

    def test_check_memory_thresholds_system_critical(self):
        """Test threshold checking with system memory critical."""
        stats = MemoryStats(
            process_memory_mb=100.0,
            process_memory_delta_mb=50.0,
            system_memory_percent=SYSTEM_MEMORY_CRITICAL_PCT + 5,
        )
        results = check_memory_thresholds(stats, "test_operation", "test_checkpoint")
        assert results["system_warning"] is True
        assert results["system_critical"] is True

    def test_check_memory_thresholds_no_system_memory(self):
        """Test threshold checking when system memory is not available."""
        stats = MemoryStats(
            process_memory_mb=100.0,
            process_memory_delta_mb=50.0,
            system_memory_percent=None,
        )
        results = check_memory_thresholds(stats, "test_operation", "test_checkpoint")
        assert results["system_warning"] is False
        assert results["system_critical"] is False


class TestLogMemoryCheckpoint:
    """Tests for log_memory_checkpoint function."""

    @patch("app.utils.memory_monitor.logger")
    def test_log_memory_checkpoint_normal(self, mock_logger):
        """Test logging memory checkpoint with normal usage."""
        stats = log_memory_checkpoint(
            "test_operation",
            "test_checkpoint",
            start_memory_mb=100.0,
            metadata={"key": "value"},
        )
        assert isinstance(stats, MemoryStats)
        # Should log at INFO level (no warnings)
        mock_logger.info.assert_called()
        # Should not log warnings
        assert not mock_logger.warning.called

    @patch("app.utils.memory_monitor.logger")
    def test_log_memory_checkpoint_with_warnings(self, mock_logger):
        """Test logging memory checkpoint with threshold warnings."""
        # Create stats that exceed thresholds
        with patch("app.utils.memory_monitor.get_memory_stats") as mock_stats:
            mock_stats.return_value = MemoryStats(
                process_memory_mb=MEMORY_WARNING_THRESHOLD_MB + 10,
                process_memory_delta_mb=MEMORY_DELTA_WARNING_MB + 10,
                system_memory_percent=SYSTEM_MEMORY_WARNING_PCT + 5,
            )
            stats = log_memory_checkpoint(
                "test_operation",
                "test_checkpoint",
                start_memory_mb=100.0,
            )
            assert isinstance(stats, MemoryStats)
            # Should log at WARNING level
            mock_logger.warning.assert_called()


class TestMemoryMonitorIntegration:
    """Integration tests for memory monitoring."""

    def test_memory_monitoring_workflow(self):
        """Test complete memory monitoring workflow."""
        # Get initial memory
        start_memory = get_memory_usage()

        # Get memory stats
        stats = get_memory_stats(start_memory_mb=start_memory)
        assert isinstance(stats, MemoryStats)

        # Check thresholds
        results = check_memory_thresholds(stats, "test_operation", "test_checkpoint")
        assert isinstance(results, dict)
        assert "process_warning" in results
        assert "process_critical" in results
        assert "delta_warning" in results
        assert "delta_critical" in results
        assert "system_warning" in results
        assert "system_critical" in results

    @patch("app.utils.memory_monitor.logger")
    def test_log_memory_checkpoint_integration(self, mock_logger):
        """Test log_memory_checkpoint integration."""
        start_memory = get_memory_usage()
        stats = log_memory_checkpoint(
            "integration_test",
            "checkpoint_1",
            start_memory_mb=start_memory,
            metadata={"test": True},
        )
        assert isinstance(stats, MemoryStats)
        # Should have logged something
        assert mock_logger.info.called or mock_logger.warning.called

    def test_get_memory_usage_with_specific_process_id(self):
        """Test get_memory_usage with specific process ID."""
        import os
        process_id = os.getpid()
        memory = get_memory_usage(process_id=process_id)
        assert isinstance(memory, float)
        assert memory >= 0.0

    @patch("app.utils.memory_monitor.psutil")
    def test_get_memory_usage_no_such_process(self, mock_psutil):
        """Test get_memory_usage handles NoSuchProcess exception."""
        import psutil
        mock_process = MagicMock()
        mock_process.memory_info.side_effect = psutil.NoSuchProcess(999)
        mock_psutil.Process.return_value = mock_process
        mock_psutil.NoSuchProcess = psutil.NoSuchProcess
        
        memory = get_memory_usage(process_id=999)
        assert memory == 0.0

    @patch("app.utils.memory_monitor.psutil")
    def test_get_memory_usage_access_denied(self, mock_psutil):
        """Test get_memory_usage handles AccessDenied exception."""
        import psutil
        mock_process = MagicMock()
        mock_process.memory_info.side_effect = psutil.AccessDenied(999)
        mock_psutil.Process.return_value = mock_process
        mock_psutil.AccessDenied = psutil.AccessDenied
        
        memory = get_memory_usage(process_id=999)
        assert memory == 0.0

    @patch("app.utils.memory_monitor.psutil")
    def test_get_system_memory_access_denied(self, mock_psutil):
        """Test get_system_memory handles AccessDenied exception."""
        import psutil
        mock_psutil.virtual_memory.side_effect = psutil.AccessDenied()
        mock_psutil.AccessDenied = psutil.AccessDenied
        
        total, available, percent = get_system_memory()
        assert total is None
        assert available is None
        assert percent is None

    @patch("app.utils.memory_monitor.psutil")
    def test_get_system_memory_general_exception(self, mock_psutil):
        """Test get_system_memory handles general exceptions."""
        mock_psutil.virtual_memory.side_effect = Exception("Unexpected error")
        
        total, available, percent = get_system_memory()
        assert total is None
        assert available is None
        assert percent is None

    def test_memory_stats_to_dict_with_none_values(self):
        """Test MemoryStats.to_dict handles None values."""
        stats = MemoryStats(
            process_memory_mb=100.0,
            process_memory_delta_mb=50.0,
            system_memory_total_mb=None,
            system_memory_available_mb=None,
            system_memory_percent=None,
            peak_memory_mb=None,
        )
        stats_dict = stats.to_dict()
        assert stats_dict["system_memory_total_mb"] is None
        assert stats_dict["system_memory_available_mb"] is None
        assert stats_dict["system_memory_percent"] is None
        assert stats_dict["peak_memory_mb"] is None

    def test_check_memory_thresholds_all_critical(self):
        """Test check_memory_thresholds with all thresholds exceeded."""
        stats = MemoryStats(
            process_memory_mb=MEMORY_CRITICAL_THRESHOLD_MB + 10,
            process_memory_delta_mb=MEMORY_DELTA_CRITICAL_MB + 10,
            system_memory_percent=SYSTEM_MEMORY_CRITICAL_PCT + 5,
        )
        results = check_memory_thresholds(stats, "test_operation")
        assert results["process_warning"] is True
        assert results["process_critical"] is True
        assert results["delta_warning"] is True
        assert results["delta_critical"] is True
        assert results["system_warning"] is True
        assert results["system_critical"] is True

    def test_check_memory_thresholds_exact_thresholds(self):
        """Test check_memory_thresholds with exact threshold values."""
        stats = MemoryStats(
            process_memory_mb=MEMORY_WARNING_THRESHOLD_MB,
            process_memory_delta_mb=MEMORY_DELTA_WARNING_MB,
            system_memory_percent=SYSTEM_MEMORY_WARNING_PCT,
        )
        results = check_memory_thresholds(stats, "test_operation")
        assert results["process_warning"] is True
        assert results["delta_warning"] is True
        assert results["system_warning"] is True

    @patch("app.utils.memory_monitor.logger")
    def test_log_memory_checkpoint_with_metadata(self, mock_logger):
        """Test log_memory_checkpoint includes metadata in logs."""
        metadata = {"custom_key": "custom_value", "another_key": 123}
        stats = log_memory_checkpoint(
            "test_operation",
            "test_checkpoint",
            metadata=metadata,
        )
        assert isinstance(stats, MemoryStats)
        # Verify metadata was included in log call
        log_calls = mock_logger.info.call_args_list + mock_logger.warning.call_args_list
        assert any("custom_key" in str(call) for call in log_calls)

    def test_get_memory_stats_with_peak(self):
        """Test get_memory_stats with peak memory tracking."""
        stats = get_memory_stats(start_memory_mb=100.0, peak_memory_mb=200.0)
        assert isinstance(stats, MemoryStats)
        assert stats.peak_memory_mb == 200.0

