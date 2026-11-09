"""Read original-ELF research through the installed GhidraMCP service.

Run with the dedicated ghidra-mcp-venv Python. Full responses stay local.
This does not execute the Android client or create game/runtime state.
"""
import argparse
import asyncio
import json
from datetime import timedelta
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL_SHA256 = '77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4'
READ_TOOLS = (
    'get_program_info', 'list_functions', 'list_segments', 'list_imports',
    'list_exports', 'list_strings', 'get_function_by_address',
    'decompile_function_by_address', 'disassemble_function', 'get_xrefs_to',
    'get_xrefs_from', 'get_function_xrefs', 'get_function_calls', 'read_memory',
)


def unpack(result):
    if result.isError:
        raise RuntimeError('GhidraMCP error: '+str(result.content))
    if result.structuredContent is not None:
        return result.structuredContent
    return json.loads(next(c.text for c in result.content if c.type == 'text'))


async def query(requests, output):
    async with streamable_http_client('http://127.0.0.1:8766/mcp') as (read, write, _):
        async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=120)) as session:
            initialize = await session.initialize()
            program = unpack(await session.call_tool('get_program_info', {}))
            if (program['sha256'] != ORIGINAL_SHA256 or
                program['language_id'] != 'AARCH64:LE:64:v8A' or int(program['image_base'], 16) != 0):
                raise ValueError('Wrong original program/architecture/image base; refusing research')
            results = []
            for request in requests:
                tool = request['tool']
                if tool not in READ_TOOLS:
                    raise ValueError('Only read tools are supported by this research helper')
                result = unpack(await session.call_tool(tool, request.get('args', {})))
                results.append({'request': request, 'result': result})
            record = {'server': initialize.serverInfo.model_dump(mode='json'),
                      'program': program, 'queries': results,
                      'scope': 'static original-ELF analysis; no rendered frame or live Android state'}
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n')
            print(json.dumps({'output': str(output), 'queries': len(results),
                              'originalSHA256': program['sha256']}))
            return record


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('tool', choices=READ_TOOLS, nargs='?')
    cli.add_argument('--args', default='{}', help='JSON parameters for one read tool')
    cli.add_argument('--batch', type=Path, help='JSON array of {tool,args} read requests')
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    if not args.output.resolve().is_relative_to((ROOT/'analysis/raw').resolve()):
        cli.error('Original decompilation and memory responses stay in ignored analysis/raw/')
    if args.batch:
        requests = json.loads(args.batch.read_text())
    elif args.tool:
        requests = [{'tool': args.tool, 'args': json.loads(args.args)}]
    else:
        cli.error('A read tool or --batch is required')
    asyncio.run(query(requests, args.output))


if __name__ == '__main__':
    main()
