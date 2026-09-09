#!/usr/bin/env bash
# Установка скиллов Hero Craft Localization в агент-хостинги на этой машине.
#
# Один каталог со скиллами (./skills) раскладывается по тем путям, которые
# агенты действительно читают. Пути взяты из официальной документации, ссылки
# на источники - в docs/compatibility.md.
#
# По умолчанию создаются символические ссылки: `git pull` в этом репозитории
# сразу обновляет установленные скиллы. `--copy` делает независимые копии.

set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
SKILLS_DIR="$SRC/skills"

MODE=link
SCOPE=user
PROJECT=""
DRY=0
FORCE=0
ACTION=install

usage() {
  cat <<'USAGE'
Использование: ./install.sh [опции]

  (без опций)          установить для текущего пользователя (символические ссылки)
  --copy               копировать файлы вместо ссылок (Windows, общие машины)
  --project КАТАЛОГ    установить в конкретный проект, а не в домашний каталог
  --list               показать найденные агенты и целевые пути, ничего не менять
  --dry-run            показать план установки, ничего не менять
  --uninstall          удалить установленные скиллы
  --force              перезаписать чужой каталог с таким же именем
  -h, --help           эта справка

Примеры:
  ./install.sh                      # для себя, все агенты на машине
  ./install.sh --copy               # без символических ссылок
  ./install.sh --project ~/game     # скиллы только внутри одного проекта
  ./install.sh --uninstall          # убрать
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --copy) MODE=copy ;;
    --link) MODE=link ;;
    --project)
      SCOPE=project
      PROJECT="${2:-}"
      [ -n "$PROJECT" ] || { echo "ошибка: --project требует каталог" >&2; exit 2; }
      shift
      ;;
    --list) ACTION=list ;;
    --dry-run) DRY=1 ;;
    --uninstall) ACTION=uninstall ;;
    --force) FORCE=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "неизвестная опция: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

# Пары "каталог|какие агенты его читают". Источники - docs/compatibility.md.
if [ "$SCOPE" = "user" ]; then
  TARGETS="$HOME/.agents/skills|Codex CLI, Cursor, OpenCode, Amp, Zed, Copilot CLI, omp
$HOME/.claude/skills|Claude Code (+ совместимость: OpenCode, Cursor, Amp)
$HOME/.gemini/skills|Gemini CLI"
else
  PROJECT="$(cd "$PROJECT" 2>/dev/null && pwd -P)" || { echo "ошибка: каталог не найден" >&2; exit 2; }
  TARGETS="$PROJECT/.agents/skills|Codex CLI, Cursor, OpenCode, Amp, Zed, Copilot CLI, omp, Gemini CLI
$PROJECT/.claude/skills|Claude Code"
fi

skill_names() {
  for d in "$SKILLS_DIR"/*/; do
    [ -f "$d/SKILL.md" ] || continue
    basename "$d"
  done
}

NAMES="$(skill_names)"
[ -n "$NAMES" ] || { echo "ошибка: в $SKILLS_DIR нет ни одного SKILL.md" >&2; exit 1; }

echo "Источник:  $SKILLS_DIR"
echo "Скиллы:    $(echo "$NAMES" | tr '\n' ' ')"
echo "Режим:     $([ "$MODE" = link ] && echo "символические ссылки" || echo "копии")"
echo

if [ "$ACTION" = "list" ]; then
  printf '%s\n' "$TARGETS" | while IFS='|' read -r dir who; do
    state="нет каталога"
    [ -d "$dir" ] && state="есть"
    printf '%-40s %-14s %s\n' "$dir" "$state" "$who"
  done
  exit 0
fi


printf '%s\n' "$TARGETS" | while IFS='|' read -r dir who; do
  echo "→ $dir"
  echo "  читают: $who"
  for name in $NAMES; do
    target="$dir/$name"
    source_path="$SKILLS_DIR/$name"

    if [ "$ACTION" = "uninstall" ]; then
      if [ -L "$target" ]; then
        resolved="$(readlink "$target")"
        if [ "$resolved" = "$source_path" ] || [ "$FORCE" = 1 ]; then
          [ "$DRY" = 1 ] && echo "  [план] удалить ссылку $name" || { rm "$target"; echo "  удалено: $name"; }
        else
          echo "  пропущено (ссылка ведёт не сюда): $name"
        fi
      elif [ -d "$target" ]; then
        if [ "$FORCE" = 1 ]; then
          [ "$DRY" = 1 ] && echo "  [план] удалить каталог $name" || { rm -rf "$target"; echo "  удалено: $name"; }
        else
          echo "  пропущено (обычный каталог, нужен --force): $name"
        fi
      fi
      continue
    fi

    verb="установлено"
    if [ -L "$target" ]; then
      # Наша же ссылка на тот же источник - ничего делать не нужно.
      if [ "$(readlink "$target")" = "$source_path" ] && [ "$MODE" = "link" ]; then
        echo "  уже установлено: $name"
        continue
      fi
      # Ссылка ведёт в другое место: это чужая установка.
      if [ "$FORCE" != 1 ]; then
        echo "  ПРОПУЩЕНО, ссылка ведёт в другое место (--force чтобы перезаписать): $name"
        continue
      fi
    elif [ -e "$target" ]; then
      # Каталог со скиллом того же имени: наша прошлая копия - обновляем,
      # что-то другое - не трогаем без --force.
      if [ "$FORCE" = 1 ]; then
        verb="перезаписано"
      elif [ -f "$target/SKILL.md" ] && grep -q "^name: *\"\{0,1\}$name\"\{0,1\} *$" "$target/SKILL.md"; then
        verb="обновлено"
      else
        echo "  ПРОПУЩЕНО, каталог занят чем-то другим (--force чтобы перезаписать): $name"
        continue
      fi
    fi

    if [ "$DRY" = 1 ]; then
      echo "  [план] $([ "$MODE" = link ] && echo ссылка || echo копия) ($verb): $name"
      continue
    fi

    mkdir -p "$dir"
    rm -rf "$target"
    if [ "$MODE" = link ]; then
      ln -s "$source_path" "$target"
    else
      cp -R "$source_path" "$target"
    fi
    echo "  $verb: $name"
  done
  echo
done

if [ "$ACTION" = "install" ] && [ "$DRY" = 0 ]; then
  cat <<'DONE'
Готово. Перезапустите агента: скиллы читаются при старте сессии, `git pull`
в уже открытой сессии ничего не изменит.

Проверка внутри агента:
  Claude Code / Copilot CLI / Gemini CLI: /skills list
  Codex CLI:  /skills        Cursor: Customize → Skills
  omp:        спросите "какие скиллы доступны"
DONE
fi
