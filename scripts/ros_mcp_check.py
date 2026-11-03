#!/usr/bin/env python3
"""Check upstream MCP -> rosbridge -> FlexCell using only a fresh Observe."""
import argparse
import asyncio
from datetime import timedelta
import json
import sys

ACTIONS = {'/observe': 'Observe', '/run_pick_place': 'RunPickPlace', '/verify_object': 'VerifyObject'}


def tool_value(reply):
    if reply.isError:
        raise RuntimeError('MCP tool error: ' + str(reply.content))
    value = getattr(reply, 'structuredContent', None)
    if value is None:
        texts = [c.text for c in reply.content if getattr(c, 'type', '') == 'text']
        value = json.loads(''.join(texts))
    if not isinstance(value, dict) or value.get('error'):
        raise RuntimeError('ROS-MCP tool failed: ' + str(value))
    return value


def observed_world(value):
    # Upstream success=True means an action result arrived, including FAILED results.
    result = value.get('result', {})
    if (value.get('success') is not True or value.get('status') != 4
            or type(result.get('outcome')) is not int or result['outcome'] != 0
            or result.get('error_code') != 0):
        raise RuntimeError('Observe did not succeed: ' + str(value))
    world = result.get('world_state', {})
    objects = world.get('objects')
    if not isinstance(objects, list) or not objects:
        raise RuntimeError('Observe returned no measured objects')
    if not all(o.get('available') is True for o in objects):
        raise RuntimeError('Observe contains unavailable objects')
    return world


async def check(args):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(command=args.server, args=['--transport', 'stdio'])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=30)) as session:
            await session.initialize()

            async def call(name, arguments):
                return tool_value(await session.call_tool(name, arguments))

            connection = await call('connect_to_robot', {'ip': args.host, 'port': args.port})
            if connection.get('connectivity_test', {}).get('port_check', {}).get('open') is not True:
                raise RuntimeError(f'rosbridge is not reachable at {args.host}:{args.port}; start bridge first')
            actions = await call('get_actions', {})
            missing = set(ACTIONS) - set(actions.get('actions', []))
            if missing:
                raise RuntimeError('Action servers are not running: ' + ', '.join(sorted(missing)))
            for name, kind in ACTIONS.items():
                details = await call('get_action_details', {
                    'action': name, 'action_type': 'flexcell_interfaces/action/' + kind})
                if not details.get('goal', {}).get('field_count') or not details.get('result', {}).get('field_count'):
                    raise RuntimeError('Missing Action definition: ' + name)
            value = await call('send_action_goal', {
                'action_name': '/observe', 'action_type': 'flexcell_interfaces/action/Observe',
                'goal': {'refresh': True, 'max_age_s': 0.0}, 'timeout': 15.0})
            world = observed_world(value)
            return {'status': 'READY', 'bridge': f'{args.host}:{args.port}',
                    'actions': ACTIONS, 'revision': world.get('revision'), 'source': world.get('source'),
                    'objects': [{'name': o['name'], 'position': o['pose']['position']}
                                for o in world['objects']],
                    'carry': world.get('carry'), 'zones': world.get('zones'),
                    'motion_dispatched': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', required=True)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=9090)
    args = parser.parse_args()
    try:
        report = asyncio.run(asyncio.wait_for(check(args), timeout=90))
    except Exception as exc:
        def explain(error):
            nested = getattr(error, 'exceptions', None)
            return '; '.join(explain(e) for e in nested) if nested else str(error) or type(error).__name__
        print(json.dumps({'status': 'NOT_READY', 'detail': explain(exc), 'motion_dispatched': False}))
        return 1
    print(json.dumps(report, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
