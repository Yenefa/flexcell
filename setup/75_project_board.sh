#!/usr/bin/env bash
# 75_project_board.sh — create GitHub Project board for FlexCell M2 and add issue items
set -u
OWNER="Yenefa"
URLS="F:/flexcell-stage/setup/74_issue_urls.txt"
TMP="${TMP:-/tmp}"

echo "== create project =="
if ! gh project create --owner "$OWNER" --title "FlexCell M2 — Decision Layer" --format json > "$TMP/proj_create.json" 2> "$TMP/proj_create.err"; then
  echo "PROJECT_CREATE_FAILED:"
  cat "$TMP/proj_create.err"
  echo "hint: gh auth refresh -s project"
  exit 4
fi
cat "$TMP/proj_create.json"
PNUM=$(python -c "import json;print(json.load(open(r'$TMP/proj_create.json'.replace(chr(92)+chr(92),chr(92))))['number'])" 2>/dev/null || python -c "import json;print(json.load(open('$TMP/proj_create.json'))['number'])")
echo "project number: $PNUM"

echo "== add items =="
ADDED=0
while IFS='|' read -r inum url title; do
  url=$(echo "$url" | tr -d ' \r')
  [ -z "$url" ] && continue
  if gh project item-add "$PNUM" --owner "$OWNER" --url "$url" > /dev/null 2>&1; then
    echo "added: $inum $url"; ADDED=$((ADDED+1))
  else
    echo "ADD_FAILED: $inum $url"
  fi
done < "$URLS"
echo "items added: $ADDED / 12"

echo "== project url =="
gh project view "$PNUM" --owner "$OWNER" --format json | python -c "import json,sys;d=json.load(sys.stdin);print(d.get('url'), '| items:', len(d.get('items',[])))" 2>/dev/null || gh project view "$PNUM" --owner "$OWNER" --web 2>/dev/null || true
