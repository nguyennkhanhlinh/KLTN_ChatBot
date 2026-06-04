"""
50 test cases đánh giá end-to-end workflow toàn hệ thống chatbot BĐS Hà Nội.

Gộp 2 nhóm chỉ số vào 1 lần chạy:
  [1] Workflow Accuracy  — routing đúng agent AND tool sequence đúng  (0/1)
  [2] Quality           — groundedness, relevance, completeness, clarity  (LLM-as-Judge)

Cấu trúc outputs:
  expected_agent         : agent supervisor phải gọi
  expected_tool_sequence : subsequence tool calls agent phải thực hiện
  difficulty             : easy / medium / hard / multi

Phân bổ:
  Analyst Agent        : 15 cases (easy 5 / medium 5 / hard 5)
  Finance Agent        : 15 cases (easy 5 / medium 5 / hard 5)
  Recommendation Agent : 15 cases (easy 5 / medium 5 / hard 5)
  Multi-agent          :  5 cases (chỉ kiểm tra routing, không check tool sequence)
"""

DATASET_NAME = "e2e_workflow_v1"

EXAMPLES = [

  
    {
        "inputs": {"question": "Top 3 quận có giá BĐS trung bình cao nhất tại Hà Nội?"},
        "outputs": {
            "expected_agent": "analyst_agent",
            "expected_tool_sequence": ["get_schema", "get_unique_values", "execute_sql"],
            "difficulty": "easy",
        },
    },
    {
        "inputs": {"question": "Số lượng tin đăng BĐS phân theo loại hình (căn hộ, nhà phố, biệt thự) tại Hà Nội?"},
        "outputs": {
            "expected_agent": "analyst_agent",
            "expected_tool_sequence": ["get_schema", "execute_sql"],
            "difficulty": "easy",
        },
    },
    {
        "inputs": {"question": "Giá trung bình mỗi m² BĐS tại quận Đống Đa là bao nhiêu?"},
        "outputs": {
            "expected_agent": "analyst_agent",
            "expected_tool_sequence": ["get_schema", "get_unique_values", "execute_sql"],
            "difficulty": "easy",
        },
    },
    {
        "inputs": {"question": "Vẽ biểu đồ cột số lượng tin đăng BĐS theo từng quận tại Hà Nội."},
        "outputs": {
            "expected_agent": "analyst_agent",
            "expected_tool_sequence": ["get_schema", "get_unique_values", "execute_sql"],
            "difficulty": "easy",
        },
    },
    {
        "inputs": {"question": "Bao nhiêu phần trăm BĐS tại Hà Nội có pháp lý sổ đỏ/sổ hồng?"},
        "outputs": {
            "expected_agent": "analyst_agent",
            "expected_tool_sequence": ["get_schema", "get_unique_values", "execute_sql"],
            "difficulty": "easy",
        },
    },


    {
        "inputs": {"question": "So sánh giá trung bình căn hộ 2PN và 3PN tại các quận nội thành Hà Nội."},
        "outputs": {
            "expected_agent": "analyst_agent",
            "expected_tool_sequence": ["get_schema", "get_unique_values", "execute_sql"],
            "difficulty": "medium",
        },
    },
    {
        "inputs": {"question": "Vẽ biểu đồ tròn thể hiện tỷ lệ loại hình BĐS tại Hà Nội."},
        "outputs": {
            "expected_agent": "analyst_agent",
            "expected_tool_sequence": ["get_schema", "execute_sql"],
            "difficulty": "medium",
        },
    },
    {
        "inputs": {"question": "Top 5 phường có giá BĐS trung bình cao nhất tại quận Cầu Giấy?"},
        "outputs": {
            "expected_agent": "analyst_agent",
            "expected_tool_sequence": ["get_schema", "get_unique_values", "execute_sql"],
            "difficulty": "medium",
        },
    },
    {
        "inputs": {"question": "Biểu đồ phân bố diện tích BĐS tại Hà Nội: dưới 50m², 50-100m², trên 100m²."},
        "outputs": {
            "expected_agent": "analyst_agent",
            "expected_tool_sequence": ["get_schema", "execute_sql"],
            "difficulty": "medium",
        },
    },
    {
        "inputs": {"question": "Quận nào có số lượng BĐS trên 10 tỷ nhiều nhất tại Hà Nội?"},
        "outputs": {
            "expected_agent": "analyst_agent",
            "expected_tool_sequence": ["get_schema", "get_unique_values", "execute_sql"],
            "difficulty": "medium",
        },
    },

    # Hard (5)
    {
        "inputs": {"question": "So sánh giá/m² BĐS giữa các quận Cầu Giấy, Đống Đa và Thanh Xuân. Quận nào đắt nhất?"},
        "outputs": {
            "expected_agent": "analyst_agent",
            "expected_tool_sequence": ["get_schema", "get_unique_values", "execute_sql"],
            "difficulty": "hard",
        },
    },
    {
        "inputs": {"question": "Biểu đồ cơ cấu nội thất (đầy đủ, cơ bản, không nội thất) theo từng quận tại Hà Nội."},
        "outputs": {
            "expected_agent": "analyst_agent",
            "expected_tool_sequence": ["get_schema", "get_unique_values", "execute_sql"],
            "difficulty": "hard",
        },
    },
    {
        "inputs": {"question": "Căn hộ dưới 3 tỷ tại Hà Nội tập trung nhiều nhất ở quận nào?"},
        "outputs": {
            "expected_agent": "analyst_agent",
            "expected_tool_sequence": ["get_schema", "get_unique_values", "execute_sql"],
            "difficulty": "hard",
        },
    },
    {
        "inputs": {"question": "Thống kê diện tích trung bình BĐS theo từng loại hình và quận tại Hà Nội."},
        "outputs": {
            "expected_agent": "analyst_agent",
            "expected_tool_sequence": ["get_schema", "get_unique_values", "execute_sql"],
            "difficulty": "hard",
        },
    },
    {
        "inputs": {"question": "Phân tích phân bổ số phòng ngủ của BĐS tại Hà Nội: bao nhiêu % có 1PN, 2PN, 3PN, 4PN+?"},
        "outputs": {
            "expected_agent": "analyst_agent",
            "expected_tool_sequence": ["get_schema", "execute_sql"],
            "difficulty": "hard",
        },
    },

  
    {
        "inputs": {"question": "Vay 1.5 tỷ trong 10 năm lãi suất 8%/năm, trả góp hàng tháng bao nhiêu?"},
        "outputs": {
            "expected_agent": "finance_agent",
            "expected_tool_sequence": ["calculate_finance"],
            "difficulty": "easy",
        },
    },
    {
        "inputs": {"question": "Nhà giá 4 tỷ, tôi có 1.5 tỷ. LTV của khoản vay là bao nhiêu?"},
        "outputs": {
            "expected_agent": "finance_agent",
            "expected_tool_sequence": ["calculate_finance"],
            "difficulty": "easy",
        },
    },
    {
        "inputs": {"question": "So sánh trả góp khi vay 2 tỷ trong 10 năm và 20 năm, lãi suất 9%/năm."},
        "outputs": {
            "expected_agent": "finance_agent",
            "expected_tool_sequence": ["compare_loan_scenarios"],
            "difficulty": "easy",
        },
    },
    {
        "inputs": {"question": "Nếu lãi suất tăng từ 9% lên 11%, khoản trả hàng tháng tăng bao nhiêu? Đang vay 2 tỷ còn 20 năm."},
        "outputs": {
            "expected_agent": "finance_agent",
            "expected_tool_sequence": ["calculate_finance"],
            "difficulty": "easy",
        },
    },
    {
        "inputs": {"question": "Thu nhập 45 triệu/tháng, vay tối đa bao nhiêu nếu muốn trả dưới 40% thu nhập, lãi 9%, 20 năm?"},
        "outputs": {
            "expected_agent": "finance_agent",
            "expected_tool_sequence": ["calculate_finance"],
            "difficulty": "easy",
        },
    },

    # Medium (5)
    {
        "inputs": {"question": "Techcombank ưu đãi 6.5%/năm trong 2 năm đầu rồi thả nổi 11%. Vay 3 tỷ trong 25 năm, PMT mỗi giai đoạn?"},
        "outputs": {
            "expected_agent": "finance_agent",
            "expected_tool_sequence": ["calculate_hybrid_rate"],
            "difficulty": "medium",
        },
    },
    {
        "inputs": {"question": "Thu nhập gia đình 70 triệu, vốn tự có 2 tỷ, muốn mua nhà 7 tỷ, lãi 9.5%, vay 25 năm. Có khả thi không?"},
        "outputs": {
            "expected_agent": "finance_agent",
            "expected_tool_sequence": ["calculate_finance"],
            "difficulty": "medium",
        },
    },
    {
        "inputs": {"question": "So sánh 2 kịch bản: vay 80% và vay 60% giá trị căn nhà 5 tỷ, lãi 9.5%/năm, thời hạn 20 năm."},
        "outputs": {
            "expected_agent": "finance_agent",
            "expected_tool_sequence": ["compare_loan_scenarios"],
            "difficulty": "medium",
        },
    },
    {
        "inputs": {"question": "Tôi đang vay 1.5 tỷ còn 15 năm lãi 9%. Nếu trả thêm 3 triệu/tháng thì tiết kiệm được bao nhiêu tiền lãi?"},
        "outputs": {
            "expected_agent": "finance_agent",
            "expected_tool_sequence": ["calculate_finance"],
            "difficulty": "medium",
        },
    },
    {
        "inputs": {"question": "Ba gói vay: Vietcombank 8.5% cố định, BIDV 7% trong 3 năm rồi thả nổi 12%, Techcombank 9.2% cố định. Vay 2 tỷ, 15 năm, cái nào tối ưu?"},
        "outputs": {
            "expected_agent": "finance_agent",
            "expected_tool_sequence": ["compare_loan_scenarios"],
            "difficulty": "medium",
        },
    },

    # Hard (5)
    {
        "inputs": {"question": "Thu nhập 20 triệu, vốn 400 triệu, lãi 9.5%, vay 20 năm. Tôi có nên vay mua nhà không và vay tối đa bao nhiêu là an toàn?"},
        "outputs": {
            "expected_agent": "finance_agent",
            "expected_tool_sequence": ["calculate_finance"],
            "difficulty": "hard",
        },
    },
    {
        "inputs": {"question": "Gia đình dự kiến có con trong 2 năm tới, cần dự phòng 15 triệu/tháng. Thu nhập hiện tại 65 triệu. Mua nhà tối đa bao nhiêu tỷ?"},
        "outputs": {
            "expected_agent": "finance_agent",
            "expected_tool_sequence": ["calculate_finance"],
            "difficulty": "hard",
        },
    },
    {
        "inputs": {"question": "Vay 3 tỷ, 30 năm, lãi 9.5%. Sau 5 năm trả trước 500 triệu. Tiết kiệm được bao nhiêu tiền lãi so với vay đủ 30 năm?"},
        "outputs": {
            "expected_agent": "finance_agent",
            "expected_tool_sequence": ["calculate_finance"],
            "difficulty": "hard",
        },
    },
    {
        "inputs": {"question": "Tôi đang thuê nhà 12 triệu/tháng. Mua nhà 4 tỷ, vay 70%, lãi 9.5%, 20 năm. Mua có lợi hơn thuê không?"},
        "outputs": {
            "expected_agent": "finance_agent",
            "expected_tool_sequence": ["calculate_finance"],
            "difficulty": "hard",
        },
    },
    {
        "inputs": {"question": "So sánh 3 kịch bản vay 10, 20, 30 năm cho khoản vay 3 tỷ lãi 9%/năm. Tổng lãi và trả hàng tháng của từng kịch bản?"},
        "outputs": {
            "expected_agent": "finance_agent",
            "expected_tool_sequence": ["compare_loan_scenarios"],
            "difficulty": "hard",
        },
    },

 
    {
        "inputs": {"question": "Tìm 3 căn hộ 2 phòng ngủ ở quận Hoàng Mai giá dưới 4 tỷ."},
        "outputs": {
            "expected_agent": "recommendation_agent",
            "expected_tool_sequence": ["get_schema", "get_unique_values", "execute_sql"],
            "difficulty": "easy",
        },
    },
    {
        "inputs": {"question": "Nhà phố 4PN ở quận Nam Từ Liêm, diện tích 100-150m², giá dưới 8 tỷ."},
        "outputs": {
            "expected_agent": "recommendation_agent",
            "expected_tool_sequence": ["get_schema", "get_unique_values", "execute_sql"],
            "difficulty": "easy",
        },
    },
    {
        "inputs": {"question": "Căn hộ 1 phòng ngủ ở Long Biên giá dưới 2.5 tỷ, có sổ đỏ."},
        "outputs": {
            "expected_agent": "recommendation_agent",
            "expected_tool_sequence": ["get_schema", "get_unique_values", "execute_sql"],
            "difficulty": "easy",
        },
    },
    {
        "inputs": {"question": "Căn hộ 3PN ở Hà Đông, nội thất đầy đủ, diện tích 90-120m², giá 3-5 tỷ."},
        "outputs": {
            "expected_agent": "recommendation_agent",
            "expected_tool_sequence": ["get_schema", "get_unique_values", "execute_sql"],
            "difficulty": "easy",
        },
    },
    {
        "inputs": {"question": "Tìm biệt thự ở quận Tây Hồ, diện tích trên 200m², pháp lý đầy đủ."},
        "outputs": {
            "expected_agent": "recommendation_agent",
            "expected_tool_sequence": ["get_schema", "get_unique_values", "execute_sql"],
            "difficulty": "easy",
        },
    },

    # Medium (5) — SQL + semantic (hybrid)
    {
        "inputs": {"question": "Căn hộ có view hồ hoặc công viên, yên tĩnh, phù hợp cho gia đình trẻ có trẻ nhỏ ở Hà Nội."},
        "outputs": {
            "expected_agent": "recommendation_agent",
            "expected_tool_sequence": ["execute_sql", "retrieve_context"],
            "difficulty": "medium",
        },
    },
    {
        "inputs": {"question": "Tìm nhà gần khu vực Cầu Giấy hoặc Dịch Vọng, 2-3PN, có chỗ để xe, giá dưới 6 tỷ."},
        "outputs": {
            "expected_agent": "recommendation_agent",
            "expected_tool_sequence": ["get_schema", "get_unique_values", "execute_sql"],
            "difficulty": "medium",
        },
    },
    {
        "inputs": {"question": "Căn hộ cao cấp full nội thất, có gym và hồ bơi, khu vực Tây Hồ hoặc Ba Đình."},
        "outputs": {
            "expected_agent": "recommendation_agent",
            "expected_tool_sequence": ["get_schema", "get_unique_values", "execute_sql", "retrieve_context"],
            "difficulty": "medium",
        },
    },
    {
        "inputs": {"question": "Nhà phố 4 tầng, mặt tiền rộng, gần trung tâm, phù hợp để ở kết hợp kinh doanh nhỏ, giá 7-12 tỷ."},
        "outputs": {
            "expected_agent": "recommendation_agent",
            "expected_tool_sequence": ["get_schema", "execute_sql", "retrieve_context"],
            "difficulty": "medium",
        },
    },
    {
        "inputs": {"question": "Căn hộ 3PN tầng cao, hướng thoáng, gần bệnh viện lớn, ở Đống Đa hoặc Hai Bà Trưng."},
        "outputs": {
            "expected_agent": "recommendation_agent",
            "expected_tool_sequence": ["get_schema", "get_unique_values", "execute_sql"],
            "difficulty": "medium",
        },
    },

    {
        "inputs": {"question": "Tôi làm việc ở Mỹ Đình, muốn sống gần thiên nhiên, yên tĩnh nhưng không quá xa trung tâm. Gợi ý nhà phù hợp."},
        "outputs": {
            "expected_agent": "recommendation_agent",
            "expected_tool_sequence": ["retrieve_context"],
            "difficulty": "hard",
        },
    },
    {
        "inputs": {"question": "Đầu tư cho thuê ngắn hạn (Airbnb-style), cần vị trí trung tâm, view đẹp, dưới 4 tỷ."},
        "outputs": {
            "expected_agent": "recommendation_agent",
            "expected_tool_sequence": ["execute_sql", "retrieve_context"],
            "difficulty": "hard",
        },
    },
    {
        "inputs": {"question": "Gia đình 3 thế hệ cần nhà rộng: tầng 1 cho ông bà (gần bệnh viện), có sân, 4-5PN."},
        "outputs": {
            "expected_agent": "recommendation_agent",
            "expected_tool_sequence": ["execute_sql", "retrieve_context"],
            "difficulty": "hard",
        },
    },
    {
        "inputs": {"question": "Căn hộ phù hợp làm việc từ xa: phòng riêng yên tĩnh, ánh sáng tự nhiên tốt, internet ổn định, giá dưới 4 tỷ."},
        "outputs": {
            "expected_agent": "recommendation_agent",
            "expected_tool_sequence": ["retrieve_context"],
            "difficulty": "hard",
        },
    },
    {
        "inputs": {"question": "Tìm nhà có phong thủy tốt: hướng nam hoặc đông nam, không đối diện ngã ba, gần trường học và chợ."},
        "outputs": {
            "expected_agent": "recommendation_agent",
            "expected_tool_sequence": ["retrieve_context"],
            "difficulty": "hard",
        },
    },


    {
        "inputs": {"question": "Thu nhập 50 triệu, vốn 1.5 tỷ, lãi 9%, vay 20 năm. Tìm căn hộ 2PN phù hợp ngân sách ở Cầu Giấy hoặc Thanh Xuân."},
        "outputs": {
            "expected_agent": ["finance_agent", "recommendation_agent"],
            "expected_tool_sequence": None,
            "difficulty": "multi",
        },
    },
    {
        "inputs": {"question": "Phân tích thị trường BĐS quận Hà Đông rồi tìm cho tôi 3 căn hộ 2PN dưới 4 tỷ ở đó."},
        "outputs": {
            "expected_agent": ["analyst_agent", "recommendation_agent"],
            "expected_tool_sequence": None,
            "difficulty": "multi",
        },
    },
    {
        "inputs": {"question": "Giá BĐS tại quận Đống Đa hiện tại như thế nào và tìm cho tôi nhà 3PN dưới 7 tỷ ở đó."},
        "outputs": {
            "expected_agent": ["analyst_agent", "recommendation_agent"],
            "expected_tool_sequence": None,
            "difficulty": "multi",
        },
    },
    {
        "inputs": {"question": "Tôi có 2 tỷ vốn, lãi 9.5%, vay 25 năm, thu nhập 45 triệu. Quận nào tại Hà Nội có BĐS phù hợp với tầm tiền của tôi?"},
        "outputs": {
            "expected_agent": ["finance_agent", "analyst_agent"],
            "expected_tool_sequence": None,
            "difficulty": "multi",
        },
    },
    {
        "inputs": {"question": "So sánh vay 15 năm và 25 năm cho khoản vay 2.5 tỷ lãi 9.5%, sau đó gợi ý căn hộ 3PN ở Hà Đông phù hợp với kịch bản tốt hơn."},
        "outputs": {
            "expected_agent": ["finance_agent", "recommendation_agent"],
            "expected_tool_sequence": None,
            "difficulty": "multi",
        },
    },
]
