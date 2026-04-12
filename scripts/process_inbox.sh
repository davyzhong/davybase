#!/bin/bash
# 散落笔记批量处理快捷脚本
# 用法：./process_inbox.sh [summarize|classify|apply|all] [limit]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MINIMAX_API_KEY="${MINIMAX_API_KEY:-sk-cp-irraUWZ84ETjyxnjefqNEyApEgJcXG0mllYHYWPZGz0OzJhNJXUZF55ZOdO09lY_aH1QxDOMucmI9Hk8G_iq8fIXVzxTYf7fSq5GPfGC3P4cR5W7hSlKEu4}"

export MINIMAX_API_KEY

COMMAND="${1:-all}"
LIMIT="${2:-}"

if [ -n "$LIMIT" ]; then
    LIMIT_ARG="--limit $LIMIT"
else
    LIMIT_ARG=""
fi

echo "============================================================"
echo "📝 散落笔记批量处理"
echo "============================================================"
echo "命令：$COMMAND"
echo "限制：${LIMIT:-无}"
echo ""

case "$COMMAND" in
    summarize)
        echo "正在生成标题..."
        python3 "$SCRIPT_DIR/summarize_and_classify.py" --summarize $LIMIT_ARG --batch-size 30
        ;;
    classify)
        echo "正在分类笔记..."
        python3 "$SCRIPT_DIR/summarize_and_classify.py" --classify $LIMIT_ARG --batch-size 30
        ;;
    apply)
        echo "正在执行分类（创建知识库并移动笔记）..."
        python3 "$SCRIPT_DIR/summarize_and_classify.py" --apply $LIMIT_ARG --auto-confirm
        ;;
    all)
        echo "步骤 1/3: 生成标题..."
        python3 "$SCRIPT_DIR/summarize_and_classify.py" --summarize $LIMIT_ARG --batch-size 30

        echo ""
        echo "步骤 2/3: 分类笔记..."
        python3 "$SCRIPT_DIR/summarize_and_classify.py" --classify $LIMIT_ARG --batch-size 30

        echo ""
        echo "步骤 3/3: 执行分类..."
        python3 "$SCRIPT_DIR/summarize_and_classify.py" --apply $LIMIT_ARG --auto-confirm
        ;;
    *)
        echo "用法：$0 [summarize|classify|apply|all] [limit]"
        echo ""
        echo "命令说明："
        echo "  summarize  - 为无标题笔记生成标题"
        echo "  classify   - 为笔记分类（生成分类标签）"
        echo "  apply      - 执行分类（创建知识库并移动笔记）"
        echo "  all        - 执行完整流程（默认）"
        echo ""
        echo "示例："
        echo "  $0 all 10        # 处理 10 条笔记的完整流程"
        echo "  $0 summarize 50  # 生成 50 条笔记的标题"
        echo "  $0 classify      # 批量分类所有待分类笔记"
        echo "  $0 apply         # 执行所有已分类笔记的迁移"
        exit 1
        ;;
esac

echo ""
echo "============================================================"
echo "✅ 处理完成"
echo "============================================================"
