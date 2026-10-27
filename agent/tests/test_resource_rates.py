import os
import sys
import time
import uuid
import pytest
from unittest import mock
import collections

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from collectors.common import SystemResourceCollector
from agent import MonitorAgent
from config import settings
import psutil

# Mock snetio
snetio = collections.namedtuple('snetio', ['bytes_sent', 'bytes_recv', 'packets_sent', 'packets_recv', 'errin', 'errout', 'dropin', 'dropout'])

@pytest.fixture
def mock_psutil():
    with mock.patch('psutil._psplatform.net_io_counters') as m_net, \
         mock.patch('psutil.cpu_percent') as m_cpu, \
         mock.patch('psutil.virtual_memory') as m_mem, \
         mock.patch('psutil.disk_partitions') as m_disk_part, \
         mock.patch('psutil.disk_usage') as m_disk_usage, \
         mock.patch('psutil.disk_io_counters') as m_disk_io, \
         mock.patch('psutil.swap_memory') as m_swap, \
         mock.patch('time.monotonic') as m_mono:
         
        m_net.return_value = {
            'eth0': (1000, 2000, 0, 0, 0, 0, 0, 0),
            'eth1': (500, 500, 0, 0, 0, 0, 0, 0)
        }
        
        m_cpu.side_effect = lambda interval=None, percpu=False: [10.0, 20.0, 30.0, 40.0] if percpu else 25.0
        
        vmem = mock.Mock()
        vmem.percent = 50.0
        vmem.available = 1024000
        m_mem.return_value = vmem
        
        swap = mock.Mock()
        swap.percent = 10.0
        swap.free = 512000
        m_swap.return_value = swap
        
        part = mock.Mock()
        part.mountpoint = '/'
        m_disk_part.return_value = [part]
        
        usage = mock.Mock()
        usage.percent = 60.0
        usage.free = 2048000
        m_disk_usage.return_value = usage
        
        m_disk_io.return_value = {
            'sda': mock.Mock(read_bytes=100, write_bytes=200, read_time=10, write_time=20)
        }
        
        m_mono.return_value = 10.0
        
        with mock.patch('psutil.process_iter') as m_proc_iter:
            m_proc_iter.return_value = []
            yield m_net, m_mono

@pytest.fixture
def temp_spool(tmp_path):
    spool_path = tmp_path / "spool.db"
    settings.SPOOL_DB_PATH = str(spool_path)
    # Ensure config allows us to test
    settings.AGENT_UID_FILE = str(tmp_path / "agent.uid")
    settings.SERVER_UID_FILE = str(tmp_path / "server.uid")
    with open(settings.AGENT_UID_FILE, "w") as f:
        f.write("test-agent-123")
    return str(spool_path)

def test_resource_rates_real_wiring(mock_psutil, temp_spool):
    m_net, m_mono = mock_psutil
    collector = SystemResourceCollector()
    
    # 1. First sample at time 10.0
    metrics1 = collector.collect()
    
    # Verify exact E2E dimensions for other metrics
    cpu_cores = [m for m in metrics1 if m['metric_code'] == 'CPU_CORE_PCT']
    assert len(cpu_cores) == 4
    for i in range(4):
        assert cpu_cores[i]['dimension_key'] == 'core'
        assert cpu_cores[i]['dimension_value'] == str(i)
        assert cpu_cores[i]['metric_value'] == float((i + 1) * 10) # 10.0, 20.0, 30.0, 40.0
    
    cpu_total = [m for m in metrics1 if m['metric_code'] == 'CPU_USAGE_PCT'][0]
    assert cpu_total['metric_value'] == 25.0
    
    if hasattr(psutil, "getloadavg"):
        assert any(m['metric_code'] == 'CPU_LOAD_1M' for m in metrics1)
    
    swap_pct = [m for m in metrics1 if m['metric_code'] == 'SWAP_USAGE_PCT'][0]
    assert swap_pct['metric_value'] == 10.0
    
    swap_avail = [m for m in metrics1 if m['metric_code'] == 'SWAP_AVAILABLE_BYTES'][0]
    assert swap_avail['metric_value'] == 512000.0
    
    disk_usage = [m for m in metrics1 if m['metric_code'] == 'DISK_USAGE_PCT'][0]
    assert disk_usage['dimension_key'] == 'path'
    assert disk_usage['dimension_value'] == '/'
    
    disk_io_read = [m for m in metrics1 if m['metric_code'] == 'DISK_IO_READ_BYTES'][0]
    assert disk_io_read['dimension_key'] == 'disk'
    assert disk_io_read['dimension_value'] == 'sda'
    assert disk_io_read['metric_value'] == 100.0
    
    disk_io_write = [m for m in metrics1 if m['metric_code'] == 'DISK_IO_WRITE_BYTES'][0]
    assert disk_io_write['metric_value'] == 200.0
    
    disk_io_read_time = [m for m in metrics1 if m['metric_code'] == 'DISK_IO_READ_TIME'][0]
    assert disk_io_read_time['metric_value'] == 10.0
    
    disk_io_write_time = [m for m in metrics1 if m['metric_code'] == 'DISK_IO_WRITE_TIME'][0]
    assert disk_io_write_time['metric_value'] == 20.0
    
    # Verify no rates on first sample
    assert not any(m['metric_code'] == 'NET_BYTES_SENT_RATE' for m in metrics1)
    
    # Verify cumulative metrics are present
    net_sent = [m for m in metrics1 if m['metric_code'] == 'NET_BYTES_SENT']
    assert len(net_sent) == 1
    assert net_sent[0]['metric_value'] == 1500.0  # 1000 + 500
    
    # 2. Second sample at time 12.0
    m_mono.return_value = 12.0
    m_net.return_value = {
        'eth0': (1200, 2200, 0, 0, 0, 0, 0, 0),  # +200 sent, +200 recv
        'eth1': (600, 700, 0, 0, 0, 0, 0, 0)     # +100 sent, +200 recv
    }
    
    metrics2 = collector.collect()
    rates2_sent = {(m['dimension_key'], m['dimension_value']): m['metric_value'] for m in metrics2 if m['metric_code'] == 'NET_BYTES_SENT_RATE'}
    rates2_recv = {(m['dimension_key'], m['dimension_value']): m['metric_value'] for m in metrics2 if m['metric_code'] == 'NET_BYTES_RECV_RATE'}
    
    assert rates2_sent[('interface', 'eth0')] == 100.0  # 200 bytes / 2 sec
    assert rates2_sent[('interface', 'eth1')] == 50.0   # 100 bytes / 2 sec
    assert rates2_recv[('interface', 'eth0')] == 100.0  # 200 bytes / 2 sec
    assert rates2_recv[('interface', 'eth1')] == 100.0  # 200 bytes / 2 sec
    
    # 3. Third sample at time 12.0 (Zero interval)
    m_mono.return_value = 12.0
    m_net.return_value = {
        'eth0': (1300, 2300, 0, 0, 0, 0, 0, 0),
        'eth1': (700, 800, 0, 0, 0, 0, 0, 0)
    }
    metrics3 = collector.collect()
    assert not any(m['metric_code'] == 'NET_BYTES_SENT_RATE' for m in metrics3)
    assert not any(m['metric_code'] == 'NET_BYTES_RECV_RATE' for m in metrics3)
    
    # 4. Fourth sample at time 11.0 (Negative interval / time wrap)
    m_mono.return_value = 11.0
    metrics4 = collector.collect()
    assert not any(m['metric_code'] == 'NET_BYTES_SENT_RATE' for m in metrics4)
    assert not any(m['metric_code'] == 'NET_BYTES_RECV_RATE' for m in metrics4)
    
    # 5. Reset/Wrap behavior (eth0 raw counter goes down, eth1 normal)
    # The cache was updated at time=11.0 with (1300, 2300).
    m_mono.return_value = 14.0
    m_net.return_value = {
        'eth0': (50, 100, 0, 0, 0, 0, 0, 0),   # 1300 -> 50 (reset)
        'eth1': (850, 950, 0, 0, 0, 0, 0, 0)   # 700 -> 850 (normal)
    }
    metrics5 = collector.collect()
    rates5_sent = {(m['dimension_key'], m['dimension_value']): m['metric_value'] for m in metrics5 if m['metric_code'] == 'NET_BYTES_SENT_RATE'}
    rates5_recv = {(m['dimension_key'], m['dimension_value']): m['metric_value'] for m in metrics5 if m['metric_code'] == 'NET_BYTES_RECV_RATE'}
    assert ('interface', 'eth0') not in rates5_sent, "Discontinuous sample should be omitted"
    assert ('interface', 'eth0') not in rates5_recv
    assert rates5_sent[('interface', 'eth1')] == 50.0  # (850 - 700) / 3 sec = 50.0
    assert rates5_recv[('interface', 'eth1')] == 50.0
    
    # 6. Rebaseline after wrap
    m_mono.return_value = 16.0
    m_net.return_value = {
        'eth0': (150, 200, 0, 0, 0, 0, 0, 0),  # 50 -> 150
        'eth1': (950, 1050, 0, 0, 0, 0, 0, 0)  # 850 -> 950
    }
    metrics6 = collector.collect()
    rates6_sent = {(m['dimension_key'], m['dimension_value']): m['metric_value'] for m in metrics6 if m['metric_code'] == 'NET_BYTES_SENT_RATE'}
    rates6_recv = {(m['dimension_key'], m['dimension_value']): m['metric_value'] for m in metrics6 if m['metric_code'] == 'NET_BYTES_RECV_RATE'}
    assert rates6_sent[('interface', 'eth0')] == 50.0  # 100 / 2 sec
    assert rates6_sent[('interface', 'eth1')] == 50.0  # 100 / 2 sec
    assert rates6_recv[('interface', 'eth0')] == 50.0
    assert rates6_recv[('interface', 'eth1')] == 50.0
    
    # 7. Disappearing interfaces (returns None/empty)
    m_mono.return_value = 18.0
    m_net.return_value = {}  # All interfaces disappear
    metrics7 = collector.collect()
    assert not any(m['metric_code'] == 'NET_BYTES_SENT_RATE' for m in metrics7)
    assert not any(m['metric_code'] == 'NET_BYTES_RECV_RATE' for m in metrics7)
    
    # 8. Recreated interfaces (first sample should be omitted, not huge spike)
    m_mono.return_value = 20.0
    m_net.return_value = {
        'eth0': (2000, 3000, 0, 0, 0, 0, 0, 0)
    }
    metrics8 = collector.collect()
    rates8_sent = {(m['dimension_key'], m['dimension_value']): m['metric_value'] for m in metrics8 if m['metric_code'] == 'NET_BYTES_SENT_RATE'}
    assert ('interface', 'eth0') not in rates8_sent, "Recreated interface should establish new baseline, no rate on first sample"
    
    # 9. Normal rate after recreation
    m_mono.return_value = 22.0
    m_net.return_value = {
        'eth0': (2200, 3200, 0, 0, 0, 0, 0, 0)
    }
    metrics9 = collector.collect()
    rates9_sent = {(m['dimension_key'], m['dimension_value']): m['metric_value'] for m in metrics9 if m['metric_code'] == 'NET_BYTES_SENT_RATE'}
    rates9_recv = {(m['dimension_key'], m['dimension_value']): m['metric_value'] for m in metrics9 if m['metric_code'] == 'NET_BYTES_RECV_RATE'}
    assert rates9_sent[('interface', 'eth0')] == 100.0
    assert rates9_recv[('interface', 'eth0')] == 100.0

    # Test full agent run with rate generation across multiple samples
    with mock.patch('requests.post') as m_post:
        m_post.return_value.status_code = 200
        m_post.return_value.json.return_value = {"data": {}}
        
        agent = MonitorAgent()
        agent.collectors = [collector]
        
        # Clear spool completely
        agent.flush_spool()
        
        # Advance time to 24.0 for collect 1
        m_mono.return_value = 24.0
        m_net.return_value = {'eth0': (2400, 3400, 0, 0, 0, 0, 0, 0)}
        agent.collect_and_spool()
        
        # Advance time to 26.0 for collect 2
        m_mono.return_value = 26.0
        m_net.return_value = {'eth0': (2600, 3600, 0, 0, 0, 0, 0, 0)}
        agent.collect_and_spool()
        
        # Spool should contain metrics from both samples, including rates
        ids, spool_items = agent.spooler.pop_batch(1000)
        assert len(spool_items) > 0
        
        flushed_network_rate_items = [
            m for m in spool_items 
            if m.get('metric_code') in ('NET_BYTES_SENT_RATE', 'NET_BYTES_RECV_RATE')
        ]
        # At least one sent and one recv rate from each of the two collections (time 24 and 26)
        assert len(flushed_network_rate_items) == 4, f"Expected 4 rate items, got {len(flushed_network_rate_items)}"
        for item in flushed_network_rate_items:
            assert item.get('dimension_key') == 'interface'
            assert item.get('dimension_value') == 'eth0'
            assert item.get('metric_value') == 100.0
            
        # Put back to spool for flush test
        agent.spooler.push(spool_items)
        
        # Test flush and reconnect failure
        m_post.return_value.status_code = 500
        agent.flush_spool()
        assert agent.spooler.get_count() > 0, "Spool should retain items on failure"
        
        # Recover
        m_post.return_value.status_code = 200
        agent.flush_spool()
        assert agent.spooler.get_count() == 0, "Spool should be empty after success"
        assert m_post.called

def test_agent_cadence():
    """Bounded scheduler/config-cadence test without real sleeps."""
    agent = MonitorAgent()
    
    with mock.patch('agent.settings.COLLECT_INTERVAL_SEC', 10):
        with mock.patch('agent.settings.HEARTBEAT_INTERVAL_SEC', 20):
            with mock.patch('time.time', side_effect=[100, 105, 110, 115, 120, 125]):
                with mock.patch.object(agent, 'collect_and_spool') as m_collect:
                    with mock.patch.object(agent, 'flush_spool') as m_flush:
                        with mock.patch.object(agent, 'send_heartbeat') as m_hb:
                            last_collect_time, last_heartbeat_time = agent._run_iteration(100, 0, 0) # initial
                            assert m_collect.call_count == 1
                            assert m_flush.call_count == 1
                            assert m_hb.call_count == 1
                            
                            last_collect_time, last_heartbeat_time = agent._run_iteration(105, last_collect_time, last_heartbeat_time)
                            assert m_collect.call_count == 1 # 105 - 100 < 10
                            
                            last_collect_time, last_heartbeat_time = agent._run_iteration(110, last_collect_time, last_heartbeat_time)
                            assert m_collect.call_count == 2 # 110 - 100 >= 10
                            assert m_hb.call_count == 1 # 110 - 100 < 20
                            
                            last_collect_time, last_heartbeat_time = agent._run_iteration(120, last_collect_time, last_heartbeat_time)
                            assert m_collect.call_count == 3
                            assert m_hb.call_count == 2 # 120 - 100 >= 20
