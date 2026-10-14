#!/usr/bin/env python3
"""Run the course validator for labs changed by a GitHub push or pull request.

Use --all locally for a full check. No dependencies beyond Python and Git.
The course validator and its schema are intentionally left unchanged.
"""

import argparse
import html
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid


ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = '.github/workflows/validate-labs.yml'
LAB = re.compile(r'^lr\d{2}_[a-zA-Z0-9_]+$')
SHA = re.compile(r'^[0-9a-fA-F]{40,64}$')


def select_scopes(paths):
    """None means a full check; otherwise return unique changed lab folders."""
    if any(p == 'README.md' or p == WORKFLOW or p.startswith('tools/')
           for p in paths):
        return None
    return sorted({p.split('/', 1)[0] for p in paths
                   if '/' in p and LAB.fullmatch(p.split('/', 1)[0])})


def changed_paths(event_name, event, root=ROOT):
    """Use a push range or a PR merge-base; None requests a conservative full run."""
    if event_name == 'workflow_dispatch':
        return None, 'Ручний запуск: повна перевірка.'
    if event_name == 'push':
        if event.get('deleted'):
            return [], 'Гілку видалено: перевіряти нічого.'
        base, head = event.get('before', ''), event.get('after', '')
        separator = '..'
        if base and set(base) == {'0'}:
            return None, 'Перший push гілки: повна перевірка.'
    elif event_name == 'pull_request':
        pr = event['pull_request']
        base, head = pr['base']['sha'], pr['head']['sha']
        separator = '...'
    else:
        raise ValueError('Потрібна подія push/pull_request/workflow_dispatch або --all.')

    if not SHA.fullmatch(base) or not SHA.fullmatch(head):
        raise ValueError('Подія не містить коректних SHA для порівняння.')
    for revision in (base, head):
        check = subprocess.run(
            ['git', 'cat-file', '-e', revision + '^{commit}'], cwd=root,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        if check.returncode:
            return None, 'Історія порівняння недоступна: повна перевірка.'

    result = subprocess.run(
        ['git', 'diff', '--name-only', '--no-renames', '-z',
         base + separator + head, '--'],
        cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    )
    paths = result.stdout.decode('utf-8', errors='surrogateescape').split('\0')
    return [p for p in paths if p], 'Порівняння: ' + base + separator + head


def write_summary(text):
    destination = os.environ.get('GITHUB_STEP_SUMMARY')
    if destination:
        with open(destination, 'a', encoding='utf-8') as handle:
            handle.write(text)


def run_validation(scopes):
    summary = ['## Перевірка лабораторних\n\n']
    if scopes == []:
        message = 'Змін у папках лабораторних або спільних файлах немає.'
        print(message)
        write_summary(summary[0] + message + '\n')
        return 0

    results = []
    for scope in ([None] if scopes is None else scopes):
        label = scope or 'Весь портфель'
        command = [sys.executable, str(ROOT / 'tools' / 'validate.py')]
        if scope:
            command.append(scope)
        print('::group::' + label, flush=True)
        result = subprocess.run(
            command, cwd=ROOT, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace',
        )
        # Validator messages contain student input; print it as plain log text.
        token = uuid.uuid4().hex
        print('::stop-commands::' + token, flush=True)
        print(result.stdout, end='' if result.stdout.endswith('\n') else '\n', flush=True)
        print('::' + token + '::', flush=True)
        print('::endgroup::', flush=True)
        results.append((label, result.returncode, result.stdout))
        if result.returncode:
            print('::error::Валідатор завершився з помилкою: ' + label, flush=True)

    summary.append('| Область | Результат |\n| --- | --- |\n')
    for label, code, _ in results:
        summary.append('| ' + label + ' | ' + ('❌ Помилка' if code else '✅ Пройдено') + ' |\n')
    for label, _, output in results:
        summary.append('\n<details><summary>' + html.escape(label) + '</summary>\n\n<pre>'
                       + html.escape(output) + '</pre>\n</details>\n')
    write_summary(''.join(summary))
    return int(any(code for _, code, _ in results))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--all', action='store_true', help='Перевірити весь портфель.')
    args = parser.parse_args()
    try:
        if args.all:
            scopes, reason = None, 'Повна перевірка (--all).'
        else:
            with open(os.environ['GITHUB_EVENT_PATH'], encoding='utf-8') as handle:
                event = json.load(handle)
            paths, reason = changed_paths(os.environ['GITHUB_EVENT_NAME'], event)
            scopes = None if paths is None else select_scopes(paths)
            if scopes is None and paths is not None:
                reason += '\nЗмінено README, workflow або tools: повна перевірка.'
        print(reason, flush=True)
        write_summary(reason + '\n\n')
        return run_validation(scopes)
    except (KeyError, ValueError, OSError, subprocess.CalledProcessError) as error:
        message = 'Не вдалося запустити перевірку: ' + str(error)
        print(message, file=sys.stderr)
        write_summary('## Помилка CI\n\n' + html.escape(message) + '\n')
        return 1


if __name__ == '__main__':
    sys.exit(main())
