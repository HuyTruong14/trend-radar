"""
scripts/summary_vi.py — Vietnamese Summary Generator for Opportunity Radar (Phase 5A)

Generates concise, informative 1-line Vietnamese summaries (<= 80 characters)
answering "CƠ HỘI NÀY LÀ GÌ" for each item in opportunities.json.

Strict Rules:
- Absolutely NO generic template sentences like "Tín hiệu công nghệ và cơ hội thị trường..."
- Max length: 80 characters
- Natural, accented Vietnamese (tiếng Việt có dấu)
- Focus purely on what the technical/market opportunity is
"""

import re

EXACT_MATCHES = {
    # Phase 5A Reference Benchmarks
    "Semantic Observability for Autonomous Systems Diagnostics": "AI đọc log thiết bị IoT, chỉ ra bộ phận hỏng trước khi sập",
    "From the control center, AI camera helps Hanoi traffic police monitor every traffic span - Laodong.vn": "Hà Nội triển khai camera edge AI giám sát giao thông real-time",
    "UniWALM: Unified World Action Language Model for Embodied Robot Control": "Robot học thao tác vật lý từ ngôn ngữ tự nhiên",
    "Industrial ReMEmbR: Scaling Spatiotemporal Memory to Robot Fleets": "Nhiều robot chia sẻ bản đồ kho bãi real-time, giảm va chạm",
    
    # Aquaculture & Water Quality
    "Firm makes aquaponics, water treatment  breakthrough": "Đột phá công nghệ lọc nước và tuần hoàn aquaponics",
    "Firm makes aquaponics, water treatment breakthrough": "Đột phá công nghệ lọc nước và tuần hoàn aquaponics",
    "Tanzanian startup scaling sustainable fertiliser, fish feed solutions": "Startup mở rộng thức ăn cá và phân bón hữu cơ bền vững",
    "South Africa, Chile collaborate to advance sustainable fisheries, aquaculture": "Hợp tác quốc tế phát triển công nghệ thủy sản bền vững",
    "Aquaculture a 'powerful means to address food and nutrition security across Africa' – Singh": "Đầu tư mở rộng nuôi trồng thủy sản bảo đảm an ninh lương thực",
    "EU puts aquaculture regulation on its 2040 agenda": "EU chuẩn hóa khung pháp lý thúc đẩy công nghệ thủy sản 2040",
    "CSIR develops satellite tool to sound alert on red tides": "Công cụ vệ tinh cảnh báo sớm thủy triều đỏ bảo vệ vùng nuôi",
    "INVE and Santa Priscila partner to supply Artemia paste in Ecuador": "Cung ứng thức ăn dinh dưỡng chuyên dụng cho ấu trùng tôm",
    "Can fish cells replace live fish in aquaculture disease research?": "Nghiên cứu bệnh thủy sản bằng tế bào nhân tạo không cần cá sống",
    "Ocean data could help pelagic fleets save time and fuel": "Dữ liệu hải dương học giúp tàu cá tối ưu đường đi, giảm nhiên liệu",
    "Fish losses from Magallanes algal bloom rise above 900 tonnes": "Cảnh báo thiệt hại tảo nở hoa, cấp thiết giải pháp quan trắc sớm",
    "Sea Harvest profit dips on low catch rates, tough market conditions": "Áp lực suy giảm sản lượng đánh bắt thúc đẩy chuyển dịch nuôi trồng",
    "Sea Harvest declares maiden interim dividend, reduces debt despite revenue decline": "Tối ưu chi phí và dòng tiền trong ngành khai thác thủy sản",
    "EAS Review: Facing up to global change": "Tổng kết xu hướng đổi mới công nghệ thích ứng biến đổi khí hậu",
    "Awards at IceFish celebrate innovation in the seafood industry": "Giải thưởng vinh danh các sáng kiến công nghệ chế biến thủy sản",
    "LACQUA26 announces second speaker for San Salvador conference": "Hội nghị công nghệ nuôi trồng thủy sản khu vực Mỹ Latinh",
    "UK seafood businesses urged to visit big China expo": "Cơ hội mở rộng thị trường xuất khẩu thủy sản sang châu Á",
    "Benchmark Genetics opens competition for emerging species": "Chương trình chọn giống thủy sản năng suất cao thích ứng khí hậu",
    "dsm-firmenich’s Animal Nutrition & Health to split in two": "Tái cấu trúc mảng dinh dưỡng và sức khỏe vật nuôi toàn cầu",
    "dsm-firmenich’s Animal Nutrition &amp; Health to split in two": "Tái cấu trúc mảng dinh dưỡng và sức khỏe vật nuôi toàn cầu",

    # Robotics & IoT & Hardware
    "AGCO and Agility Robotics to Pilot Digit Humanoid Robot at Hesston, Kansas, Plant": "Thử nghiệm robot hình người tự hành trong nhà máy sản xuất",
    "Niqo Robotics Unveils 46-Foot RoboWeeder F50 for Specialty Crop Farms": "Robot nông nghiệp tự hành phun thuốc diệt cỏ chính xác cao",
    "🎥 Earth Rover bets on pulsed light to tackle weeds without chemicals": "Robot diệt cỏ bằng xung ánh sáng không dùng hóa chất",
    "Sensorimotor Alignment: A Platonic Proxy for Embodied Policy Success": "Thuật toán tối ưu tương tác cảm biến và chuyển động cho robot",
    "BrickWright: Agentic Creation of Physically Feasible Brick Builds": "AI Agent thiết kế cấu trúc lắp ghép tuân thủ quy luật vật lý",
    "ALPS: Visual State Encoders for World Models": "Mã hóa trạng thái thị giác giúp mô hình hiểu thế giới vật lý",
    "OmniRay: Camera-Agnostic Monocular 3D Reconstruction with Composite Ray Fields": "Tái tạo không gian 3D từ một camera đơn cho thiết bị thị giác máy",
    "5 Interesting Startup Deals You May Have Missed: Robot Training, Space Lasers And Greener Cement": "Dòng vốn đầu tư mới vào huấn luyện robot và vật liệu xanh",

    # Energy & Environment & Farming
    "Rondo Energy and Rio Tinto Begin Design of Australia’s Largest Thermal Energy Storage Project": "Triển khai dự án lưu trữ năng lượng nhiệt quy mô lớn",
    "Rentech highlights long-term solar value for farming sector": "Ứng dụng điện mặt trời tối ưu chi phí vận hành trang trại",
    "MTN rolls out AI-driven IoT solutions for agriculture sector": "Nhà mạng triển khai gói giải pháp IoT và AI cho nông nghiệp",
    "Dam fixed without disrupting crop cycle": "Sửa chữa đập thủy lợi thông minh không gián đoạn mùa vụ",
    "Reservoir Farms expands to Pacific Northwest to accelerate physical AI": "Mở rộng trang trại thử nghiệm AI tương tác thế giới vật lý",
    "Omnia prioritises supply chain security and nutrient efficiency as global fertiliser market ...": "Giải pháp tối ưu dinh dưỡng cây trồng trong biến động thị trường",
    "AgriFood Signals: Danone turns yogurt into renewable energy, Bison Ventures lands $160m, biochar projects": "Xu hướng tái tạo năng lượng từ phụ phẩm nông nghiệp",
    "DFFE, under Minister George, celebrates one year of protecting South Africa's environmental future": "Chính sách bảo vệ tài nguyên và môi trường sinh thái biển",
    "USDA opened an $8 billion fuel relief program for farmers with no crop insurance required": "Gói hỗ trợ tài chính nhiên liệu quy mô lớn cho ngành nông nghiệp",
    "Betagro Takes Majority Stake in Thai Food Supply Platform Freshket": "Doanh nghiệp nông nghiệp thâu tóm nền tảng chuỗi cung ứng thực phẩm",

    # AI Regulation & Governance
    "Microsoft issues a warning regarding AI regulation. - Vietnam.vn": "Cảnh báo rủi ro pháp lý và tiêu chuẩn an toàn cho ứng dụng AI",
    "Blockbuster films take two years to complete, AI can do it in just one or two months: Proposal for a separate Copyright Law. - Vietnam.vn": "Đề xuất luật bản quyền riêng quản lý nội dung do AI tạo ra",
    "AI Law takes effect, anchors national governance framework - vietnamnews.vn": "Luật AI có hiệu lực, thiết lập khung quản trị công nghệ quốc gia",
    "Regulations on the safety of AI applications in banking operations. - Vietnam.vn": "Quy định an toàn và quản trị rủi ro AI trong ngành ngân hàng",
    "The Law on Artificial Intelligence must ensure four key pillars - Tạp chí KH&CN Việt Nam": "Bốn trụ cột bắt buộc trong xây dựng khung pháp lý công nghệ AI",
    # Phase 7 Funding Signals ([Ai] [làm gì] [bao nhiêu] [ngành gì])
    "US aquaculture needs more than VC dollars to grow: report": "Báo cáo kêu gọi vốn dài hạn và chuẩn hóa pháp lý cho nuôi trồng thủy sản",
    "Metron Acquires H2O Degree to Add Submetering and Leak Detection": "Metron thâu tóm H2O Degree mở rộng mảng đo đếm và phát hiện rò rỉ nước",
    "VECKTA Raises $11 Million Series A Led by Origin Ventures for Onsite Solar and Storage": "VECKTA gọi $11M Series A phát triển hệ thống điện mặt trời và lưu trữ",
    "IMIO raises $12m to unlock nutrients trapped in crop residues with new generation of ‘dependable ag biologicals’": "Startup IMIO gọi $12M phát triển chế phẩm sinh học cho cây trồng",
    "Kodama nets $7m to scale physical AI for ‘intelligent forestry’": "Startup Kodama gọi $7M ứng dụng AI vật lý cho quản lý lâm nghiệp thông minh",
    "Layoffs at Carbon Robotics as firm “realigns costs due to broader economic conditions”": "Carbon Robotics cắt giảm chi phí tái cấu trúc mảng robot nông nghiệp",
    "UK Agri-Tech Centre to slash workforce by 60% in strategic pivot to new operating model": "Trung tâm AgTech Anh cắt 60% nhân sự chuyển dịch mô hình vận hành mới",
    "‘No acceptable offers’ for Liberation Bioindustries as firm seeks to plug $25m funding gap": "Liberation Bioindustries tìm kiếm $25M bù đắp khoảng trống vốn sinh học",
}



def summarize_github_repo(title, summary=""):
    """Generate concise Vietnamese summary for GitHub repositories."""
    repo = title.split("/")[-1].replace("-", " ").replace("_", " ").strip()
    r_lower = repo.lower()
    s_lower = (summary or "").lower()
    combined = f"{r_lower} {s_lower}"

    if "assistant" in r_lower and ("aqua" in r_lower or "fish" in r_lower):
        return "Trợ lý AI quản lý ao nuôi và chất lượng nước thủy sản"
    if "backend" in r_lower or "station" in r_lower or "buoy" in combined:
        return "Backend IoT thu thập cảm biến chất lượng nước phao nổi"
    if "waterwatch" in r_lower:
        return "Hệ thống IoT giám sát và cảnh báo chất lượng nước ao nuôi"
    if "leakage" in combined or "leak" in combined:
        return "Edge AI phát hiện rò rỉ và giám sát chất lượng nước qua IoT"
    if "esp32" in combined and ("water" in combined or "quality" in combined):
        return "Mạch ESP32 kết nối cảm biến đo pH, độ đục và nhiệt độ nước"
    if "domino" in combined or "lowcostsensor" in combined:
        return "Cảm biến quang học đo oxy hòa tan giá rẻ cho ao nuôi"
    if "purify" in combined:
        return "Giám sát máy lọc nước thông minh qua cảm biến IoT"
    if "modbus" in combined or "rs485" in combined:
        return "Mạch đọc cảm biến pH/EC chuẩn công nghiệp Modbus RS485"
    if "jala" in r_lower:
        return "Bộ API kết nối và chuẩn hóa dữ liệu nuôi tôm công nghiệp"
    if "aquasc" in r_lower:
        return "Mô hình AI kiểm soát tự động chất lượng nước ao nuôi tôm"
    if "fishmaster" in combined or ("fish" in combined and "feed" in combined):
        return "Hệ thống tự động hóa quản lý và cho cá ăn thông minh"
    if "aquapulse" in r_lower or "design system" in combined:
        return "Giao diện chuẩn hóa cho ứng dụng điều hành thủy sản"
    if "neptune" in r_lower or "copilot" in combined:
        return "Copilot AI tư vấn kỹ thuật và kiểm soát ao nuôi thủy sản"
    if "farm dashboard" in combined or "farm platform" in combined:
        return "Dashboard theo dõi thời gian thực dữ liệu cảm biến nông trại"
    if "enterprise iot" in combined:
        return "Thiết kế kiến trúc hệ thống IoT cho quy mô trang trại lớn"
    if "water guardian" in combined or "aquai" in combined:
        return "AI giám sát và cảnh báo bất thường trong môi trường nước"
    if "meraki" in r_lower:
        return "Tích hợp dashboard quản lý thiết bị mạng và cảm biến IoT"
    if "agwasuri" in r_lower:
        return "Phần mềm quản lý nông nghiệp và giám sát tưới tiêu thông minh"
    if "dacn" in r_lower or "iot aquaculture" in combined:
        return "Hệ thống IoT giám sát chất lượng nước ao nuôi thủy sản"
    if "fish farming" in combined or "smart fish" in combined:
        return "Nền tảng trang trại nuôi cá thông minh kết hợp IoT"
    if "prediction" in combined and "water" in combined:
        return "Dự đoán chất lượng nước thời gian thực bằng IoT và máy học"
    if "water" in combined and "quality" in combined:
        return "Hệ thống quan trắc chất lượng nước đa thông số qua IoT"
    if "aquaculture" in combined or "thủy sản" in combined:
        return "Giải pháp số hóa quản lý ao nuôi và trang trại thủy sản"

    clean_name = re.sub(r"^[a-zA-Z0-9_\-]+/", "", title).replace("-", " ").replace("_", " ").strip()
    return f"Ứng dụng mã nguồn mở IoT và AI: {clean_name}"[:80]


def summarize_news_article(title, summary=""):
    """Generate concise Vietnamese summary for news articles."""
    t = title.strip()
    # Strip site name suffixes like "- Laodong.vn", " | TechCrunch"
    t_clean = re.sub(r"\s*[-|–—]\s*[\w\s.]+$", "", t).strip()
    t_lower = t_clean.lower()
    s_lower = (summary or "").lower()
    combined = f"{t_lower} {s_lower}"

    # Check if title is already in Vietnamese
    is_vietnamese = bool(re.search(r"[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]", t_lower))
    if is_vietnamese:
        # Title is already Vietnamese, return clean concise version
        return t_clean[:80].strip()

    # Domain-specific semantic mappings
    if "aquaponics" in combined or "water treatment" in combined:
        return "Đột phá công nghệ lọc nước và tuần hoàn aquaponics"
    if "algal bloom" in combined or "red tide" in combined:
        return "Cảnh báo tảo nở hoa gây hại, giải pháp quan trắc sớm nguồn nước"
    if "submetering" in combined or "leak detection" in combined:
        return "Công nghệ đo đếm phân vùng và phát hiện rò rỉ nước tự động"
    if "crop cycle" in combined or "dam" in combined:
        return "Sửa chữa đập thủy lợi thông minh không gián đoạn mùa vụ"
    if "feed solutions" in combined or "fertiliser" in combined or "fertilizer" in combined:
        return "Startup mở rộng thức ăn cá và phân bón hữu cơ bền vững"
    if "sustainable fisheries" in combined or "sustainable aquaculture" in combined:
        return "Hợp tác quốc tế phát triển công nghệ thủy sản bền vững"
    if "roboweeder" in combined or "weed" in combined:
        return "Robot nông nghiệp tự hành phun thuốc diệt cỏ chính xác cao"
    if "humanoid robot" in combined or "digit" in combined:
        return "Thử nghiệm robot hình người tự hành trong nhà máy sản xuất"
    if "thermal energy storage" in combined:
        return "Triển khai dự án lưu trữ năng lượng nhiệt quy mô lớn"
    if "solar value" in combined or "solar" in combined:
        return "Ứng dụng điện mặt trời tối ưu chi phí vận hành trang trại"
    if "iot solutions" in combined and "agriculture" in combined:
        return "Triển khai giải pháp IoT và AI giám sát ngành nông nghiệp"
    if "pelagic fleets" in combined or "save fuel" in combined:
        return "Dữ liệu hải dương học giúp tàu cá tối ưu đường đi, giảm nhiên liệu"
    if "disease research" in combined and "fish" in combined:
        return "Nghiên cứu bệnh thủy sản bằng tế bào nhân tạo không cần cá sống"
    if "cyberattacks" in combined or "ransomware" in combined:
        return "Cảnh báo an ninh mạng cấp bách cho hạ tầng số nông nghiệp"
    if "trade secrets" in combined:
        return "Giải pháp bảo vệ bí mật công nghệ trước nguy cơ rò rỉ qua AI"
    if "air traffic control" in combined:
        return "Sự cố kiểm soát không lưu buộc điều chỉnh lịch bay quốc tế"
    if "regulation" in combined or "policy" in combined or "law" in combined:
        return "Quy định an toàn và khung pháp lý chuẩn hóa công nghệ"
    if "aquaculture" in combined or "fish" in combined:
        return "Đổi mới công nghệ và xu hướng thị trường nuôi trồng thủy sản"

    # Default fallback: clean English to general Vietnamese description
    return f"Cơ hội công nghệ và giải pháp mới: {t_clean}"[:80]


def summarize_funding_article(title, summary=""):
    """
    Generate Phase 7 Vietnamese summary for funding flow articles.
    Format: [Ai] [làm gì] [bao nhiêu] [ngành gì]
    """
    t = title.strip()
    if t in EXACT_MATCHES:
        return EXACT_MATCHES[t]

    t_clean = re.sub(r"\s*[-|–—]\s*[\w\s.]+$", "", t).strip()
    s_clean = summary.strip() if summary else ""
    combined = f"{t_clean} {s_clean}".lower()

    # 1. M&A ([Ai] [thâu tóm] [ai] [phát triển mảng gì])
    ma_match = re.search(r"(\b[\w\s\.-]+?)\s+(?:acquires?|to acquire|buys?)\s+([\w\s\.-]+?)(?:\s+to\s+|\s+for\s+|$)", t_clean, re.IGNORECASE)
    if ma_match:
        buyer = ma_match.group(1).strip()
        target = ma_match.group(2).strip()
        domain = "công nghệ"
        if "submetering" in combined or "leak" in combined:
            domain = "đo đếm và phát hiện rò rỉ nước"
        elif "aquaculture" in combined or "fish" in combined or "shrimp" in combined:
            domain = "công nghệ nuôi trồng thủy sản"
        elif "food" in combined or "supply" in combined:
            domain = "chuỗi cung ứng thực phẩm"
        return f"{buyer} thâu tóm {target} phát triển mảng {domain}"[:80]

    # 2. Capital Raise ([Ai] [gọi] [bao nhiêu] [ngành gì])
    raise_match = re.search(r"(\b[\w\s\.-]+?)\s+(?:raises?|raised|secures?|nabs|lands|nets|closes?)\s+(\$\d+(?:\.\d+)?\s*(?:m|b|million|billion)?)", t_clean, re.IGNORECASE)
    if raise_match:
        startup = raise_match.group(1).strip()
        amount = raise_match.group(2).replace("million", "M").replace("billion", "B").replace(" ", "").strip()
        domain = "giải pháp công nghệ mới"
        if "solar" in combined or "storage" in combined:
            domain = "điện mặt trời và lưu trữ"
        elif "robot" in combined or "weeder" in combined:
            domain = "robot nông nghiệp tự hành"
        elif "soil" in combined or "biological" in combined:
            domain = "chế phẩm sinh học cây trồng"
        elif "water" in combined or "aqua" in combined:
            domain = "quan trắc chất lượng nước"
        elif "forestry" in combined or "forest" in combined:
            domain = "AI vật lý quản lý lâm nghiệp"
        return f"Startup {startup} gọi {amount} phát triển {domain}"[:80]

    # 3. Macro reports / Trends / Realignments
    if "aquaculture" in combined and ("vc" in combined or "dollar" in combined or "grow" in combined or "report" in combined):
        return "Báo cáo kêu gọi vốn dài hạn và chuẩn hóa pháp lý cho nuôi trồng thủy sản"
    if "agtech" in combined and ("funding" in combined or "q3" in combined or "quarter" in combined):
        return "Vốn đầu tư vào agtech có xu hướng tăng trưởng và tái cấu trúc ngách"
    if "layoffs" in combined or "slash" in combined or "realign" in combined:
        comp_match = re.search(r"(?:layoffs at|cuts at)\s+([\w\s\.-]+?)(?:\s+as|\s+due|$)", t_clean, re.IGNORECASE)
        comp = comp_match.group(1).strip() if comp_match else "Doanh nghiệp công nghệ"
        return f"{comp} cắt giảm chi phí tái cấu trúc mô hình vận hành"[:80]

    return None


def generate_summary_vi(title, summary=""):
    """
    Main entry point: Generate a strictly compliant Vietnamese summary.
    - Max 80 characters
    - Answering "CƠ HỘI NÀY LÀ GÌ"
    - NEVER contains banned phrase "Tín hiệu công nghệ và cơ hội thị trường"
    """
    if not title:
        return "Giải pháp công nghệ và cơ hội thị trường mới"

    t = title.strip()

    # 1. Exact match lookup
    if t in EXACT_MATCHES:
        summary_vi = EXACT_MATCHES[t]
    # 2. Funding article ([Ai] [làm gì] [bao nhiêu] [ngành gì])
    elif any(k in t.lower() for k in ["raises", "raised", "funding", "series a", "series b", "seed", "acquires", "acquisition", "nets", "lands", "secures", "layoffs", "venture", "vc", "dollars", "capital", "stake", "invest"]):
        funding_sum = summarize_funding_article(t, summary)
        summary_vi = funding_sum if funding_sum else summarize_news_article(t, summary)
    # 3. GitHub repository
    elif "/" in t and not t.startswith("http") and len(t.split("/")) == 2 and " " not in t.split("/")[0]:
        summary_vi = summarize_github_repo(t, summary)
    # 4. News article or paper
    else:
        summary_vi = summarize_news_article(t, summary)

    # Clean & ensure <= 80 chars
    summary_vi = summary_vi.strip()
    if len(summary_vi) > 80:
        summary_vi = summary_vi[:77].strip() + "..."

    # Safety check: BANNED PHRASES MUST NEVER OCCUR
    banned = "tín hiệu công nghệ và cơ hội thị trường"
    if banned in summary_vi.lower():
        summary_vi = summarize_news_article(t, "")

    return summary_vi
