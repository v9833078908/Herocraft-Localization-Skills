# Совместимость: где какой агент ищет скиллы

Скилл - это каталог с файлом `SKILL.md` по открытому стандарту
[Agent Skills](https://agentskills.io/specification). Формат один, а пути
разные. Ниже - только то, что написано в официальной документации каждого
инструмента; догадок в таблице нет.

`install.sh` раскладывает скиллы по трём каталогам, и этого достаточно для
восьми агентов из списка:

| Каталог | Кто его читает |
|---|---|
| `~/.agents/skills/` | Codex CLI, Cursor, OpenCode, Amp, Zed, Copilot CLI, omp |
| `~/.claude/skills/` | Claude Code (а также OpenCode, Cursor, Amp - как совместимый путь) |
| `~/.gemini/skills/` | Gemini CLI |

## Полная таблица

| Агент | Личные скиллы (весь компьютер) | Скиллы проекта | Особенности | Источник |
|---|---|---|---|---|
| Claude Code | `~/.claude/skills/<имя>/SKILL.md` | `.claude/skills/<имя>/SKILL.md`, плюс вложенные каталоги | Каталог скилла может быть символической ссылкой. Изменения подхватываются без перезапуска. Приоритет: enterprise > личные > проект | <https://code.claude.com/docs/en/skills> |
| OpenAI Codex CLI | `~/.agents/skills/` | `.agents/skills/` от текущего каталога до корня репозитория; `/etc/codex/skills` для всей машины | Символические ссылки поддерживаются. Начальный список скиллов ограничен 2% контекста или 8000 символов - длинные `description` урезаются | <https://developers.openai.com/codex/skills> |
| Cursor | `~/.agents/skills/`, `~/.cursor/skills/`, плюс `~/.claude/skills/` и `~/.codex/skills/` | `.agents/skills/`, `.cursor/skills/`, плюс `.claude/skills/` и `.codex/skills/` | Каталог скиллов обходится рекурсивно, вложенные группы разрешены. `name` обязан совпадать с именем каталога | <https://cursor.com/docs/skills> |
| OpenCode | `~/.config/opencode/skills/`, `~/.claude/skills/`, `~/.agents/skills/` | `.opencode/skills/`, `.claude/skills/`, `.agents/skills/` | Неизвестные поля frontmatter игнорируются. `name`: 1-64 символа, совпадает с каталогом; `description`: 1-1024 символа | <https://opencode.ai/docs/skills/> |
| Gemini CLI | `~/.gemini/skills/` | `.gemini/skills/`, а также псевдоним `.agents/skills/` | Только один уровень вложенности. Frontmatter обязан быть в самом начале файла, иначе скилл молча пропускается. Проектные скиллы требуют `/trust`. Команды: `/skills list`, `/skills reload` | <https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/tutorials/skills-getting-started.md> |
| GitHub Copilot CLI | `~/.copilot/skills/`, `~/.agents/skills/` | `.github/skills/`, `.claude/skills/`, `.agents/skills/` | Имя файла строго `SKILL.md`. Перечитать в сессии: `/skills reload`; посмотреть: `/skills list` | <https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-skills> |
| Amp | `~/.config/agents/skills/`, `~/.agents/skills/`, `~/.config/amp/skills/`, `~/.claude/skills/` | `.agents/skills/`, `.claude/skills/` в проекте и родительских каталогах | Побеждает первый скилл с данным `name` в порядке из документации. Имя каталога и `name` обязаны совпадать | <https://ampcode.com/docs/markdown/customize/skills> |
| Zed | `~/.agents/skills/` | `<worktree>/.agents/skills/` | Только плоская раскладка: вложенные группы не находятся. Каталог скиллов - 50 КБ на все имена и описания. Для другого расположения документация предлагает символическую ссылку | <https://zed.dev/docs/ai/skills> |
| omp (Oh My Pi) | `~/.omp/agent/skills/`, `~/.agents/skills/` | `.omp/skills/`, `.agents/skills/` | Поиск нерекурсивный: строго `<корень>/<имя>/SKILL.md`. Для нативного `.omp`-провайдера `description` обязателен | <https://github.com/can1357/oh-my-pi/blob/main/docs/skills.md> |
| Windsurf | не подтверждено официальной документацией | не подтверждено официальной документацией | Функция Skills описана только в зеркале документации Cognition, на основном сайте windsurf.com контракта путей нет. Пока путь не подтверждён, `install.sh` в Windsurf не устанавливает ничего | - |

## Символические ссылки или копии

`install.sh` по умолчанию создаёт символические ссылки: `git pull` в этом
репозитории обновляет скиллы сразу во всех агентах. Ссылки прямо описаны в
документации Claude Code, Codex CLI и Zed; остальные агенты просто читают
файлы по пути, и ссылка для них прозрачна.

Копии нужны в двух случаях: Windows без прав на создание ссылок и общая
машина, где домашний каталог не должен зависеть от чужого репозитория. Тогда:

```sh
./install.sh --copy      # и повторять после каждого git pull
```

## Ограничения, из-за которых нельзя просто «скопировать одну папку всюду»

1. **Claude Code не читает `AGENTS.md`** - только `CLAUDE.md`
   (<https://github.com/anthropics/claude-code/issues/34235>). В этом
   репозитории `CLAUDE.md` - символическая ссылка на `AGENTS.md`, чтобы
   содержимое не разъезжалось.
2. **Вложенность.** Zed, omp и Gemini CLI находят только
   `<корень>/<имя>/SKILL.md`. Раскладка `<корень>/группа/<имя>/SKILL.md`
   работает лишь в Cursor и Claude Code, поэтому в репозитории каталог
   `skills/` плоский.
3. **Регистр имени файла.** Строго `SKILL.md`: `skill.md` игнорируется на
   файловых системах, чувствительных к регистру.
4. **`name` = имя каталога.** Иначе скилл либо не загрузится, либо загрузится
   под другим именем (Gemini CLI берёт имя из поля `name`, остальные - из
   каталога).
5. **Бюджеты на описания.** Codex CLI урезает `description` при переполнении
   лимита в 2% контекста / 8000 символов, Zed отбрасывает скиллы после 50 КБ
   каталога. Поэтому описания короткие, а подробности - в теле `SKILL.md`.
6. **Нестандартные поля frontmatter.** OpenCode их игнорирует, часть агентов
   поддерживает свои расширения. В этом репозитории используются только
   `name` и `description` из открытого стандарта - это проверяет
   `tools/validate_skills.py`.
7. **Скиллы читаются при старте сессии.** Claude Code, Copilot CLI, Gemini CLI
   и Amp умеют перечитывать их на ходу, остальные - нет. После установки
   перезапустите агента.
