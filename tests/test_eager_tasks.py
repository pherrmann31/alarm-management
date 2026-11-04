"""HA eagerly-started output workers must not starve the event loop on unload.

Each liveness scenario runs in a separate process with an external watchdog:
an asyncio timeout cannot detect a loop that never yields.
"""
from pathlib import Path
import subprocess
import sys
import unittest

CHILD=r'''
import asyncio
import sys
import types
from unittest.mock import AsyncMock
sys.path.insert(0,sys.argv[1])
import test_live_outputs as live
import test_notifications as notifications
import test_platforms as platforms

async def main():
    scenario=sys.argv[2]
    loop=asyncio.get_running_loop()
    factory=loop.get_task_factory()
    if scenario=='missing_plan':
        manager=types.SimpleNamespace(hass=types.SimpleNamespace(async_create_task=asyncio.create_task),running=True,
            outputs=(types.SimpleNamespace(id='output',notification=None),),session=types.SimpleNamespace(output_plan={},executions={}))
        executor=live.live.LiveOutputExecutor(manager)
    else:
        harness=notifications.NotificationExecutionTests() if scenario=='notification_idle' else live.LiveExecutionTests()
        manager,output=await (harness.manager(source_on=False) if scenario=='notification_idle' else harness.make_manager())
        executor=manager.executor
        executor.start()
        await manager.async_drain()
    loop.set_task_factory(asyncio.eager_task_factory)
    try:
        executor.start()
        if scenario=='unload':
            manager.hass.config_entries=types.SimpleNamespace(async_unload_platforms=AsyncMock(return_value=True))
            manager.hass.services.async_remove=lambda *args:None
            entry=types.SimpleNamespace(runtime_data=manager)
            assert await platforms.lifecycle.async_unload_entry(manager.hass,entry)
        else:
            await executor.drain()
        assert not executor._tasks, executor._tasks
        heartbeat=[]
        loop.call_soon(heartbeat.append,'responsive')
        await asyncio.sleep(0)
        assert heartbeat==['responsive']
        print('PASS '+scenario,flush=True)
    finally:
        executor.stop()
        loop.set_task_factory(factory)

asyncio.run(main())
'''


class EagerTaskLivenessTests(unittest.TestCase):
    def run_case(self,scenario):
        tests=Path(__file__).parent
        result=subprocess.run([sys.executable,'-B','-u','-c',CHILD,str(tests),scenario],capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('PASS '+scenario,result.stdout)

    def test_completed_eager_worker_with_missing_plan_drains(self):
        self.run_case('missing_plan')

    def test_unchanged_confirmed_delivery_drains_with_eager_start(self):
        self.run_case('unchanged')

    def test_silent_notification_drains_with_eager_start(self):
        self.run_case('notification_idle')

    def test_integration_unload_finishes_and_loop_remains_responsive(self):
        self.run_case('unload')
