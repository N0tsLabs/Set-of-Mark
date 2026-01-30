#!/bin/bash
#
# OCR-SoM API 集成测试
#
# Usage:
#   1. 先启动服务: python server.py --port 5001
#   2. 运行测试: ./tests/test_api.sh
#

API_URL="${API_URL:-http://localhost:5001}"

echo "============================================================"
echo "  OCR-SoM API Integration Tests"
echo "============================================================"
echo "  API URL: $API_URL"
echo ""

# 颜色
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

PASS=0
FAIL=0

test_endpoint() {
    local name="$1"
    local method="$2"
    local endpoint="$3"
    local data="$4"
    local expected="$5"
    
    echo -n "  Testing $name... "
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s "$API_URL$endpoint")
    else
        response=$(curl -s -X POST "$API_URL$endpoint" \
            -H "Content-Type: application/json" \
            -d "$data")
    fi
    
    if echo "$response" | grep -q "$expected"; then
        echo -e "${GREEN}PASS${NC}"
        ((PASS++))
    else
        echo -e "${RED}FAIL${NC}"
        echo "    Expected: $expected"
        echo "    Got: $response"
        ((FAIL++))
    fi
}

# 测试健康检查
test_endpoint "GET /health" "GET" "/health" "" '"status":"ok"'

# 测试信息端点
test_endpoint "GET /info" "GET" "/info" "" '"name":"OCR-SoM"'

# 测试 OCR 无图片
test_endpoint "POST /ocr (no image)" "POST" "/ocr" '{}' '"success":false'

# 测试 OCR 不存在的文件
test_endpoint "POST /ocr (bad path)" "POST" "/ocr" '{"image_path":"/nonexistent.png"}' '"success":false'

# 如果有 demo.png，测试实际 OCR
DEMO_IMAGE="$(dirname "$0")/../docs/demo.png"
if [ -f "$DEMO_IMAGE" ]; then
    # 需要用绝对路径
    ABS_PATH=$(cd "$(dirname "$DEMO_IMAGE")" && pwd)/$(basename "$DEMO_IMAGE")
    test_endpoint "POST /ocr (demo image)" "POST" "/ocr" "{\"image_path\":\"$ABS_PATH\"}" '"success":true'
    test_endpoint "POST /som (demo image)" "POST" "/som" "{\"image_path\":\"$ABS_PATH\"}" '"success":true'
fi

# 结果
echo ""
echo "============================================================"
echo "  Results: ${GREEN}$PASS passed${NC}, ${RED}$FAIL failed${NC}"
echo "============================================================"

if [ $FAIL -gt 0 ]; then
    exit 1
fi
