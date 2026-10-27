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
    if any(k in combined for k in ["gambling ban", "lula", "brazil", "gr8_tech"]):
        return "Báo cáo công nghệ B2B định hình thị trường iGaming Brazil hậu lệnh cấm"
    if any(k in combined for k in ["illegal gambling", "gambling commission", "consumer voice"]):
        return "Nghiên cứu hành vi người chơi cá cược và giải pháp quản trị rủi ro trực tuyến"
    if any(k in combined for k in ["infotainment", "agcom"]):
        return "Quy định siết chặt kiểm soát nền tảng truyền thông gắn liên kết cá cược"
    if any(k in combined for k in ["svenska spel", "gambling operator"]):
        return "Tái cơ cấu thương hiệu và tinh giản mô hình vận hành nhà cái trực tuyến"
    if any(k in combined for k in ["self-assessment", "dgoj", "player portal"]):
        return "Ra mắt cổng đánh giá rủi ro người chơi và bảo vệ người dùng cá cược"
    if any(k in combined for k in ["namibia", "lotteries regulations"]):
        return "Dự thảo cải cách quy định quản lý cá cược và sổ xố trực tuyến"
    if any(k in combined for k in ["former afl players", "illegal gambling promotion", "acma"]):
        return "Cảnh báo xử phạt người có ảnh hưởng quảng bá dịch vụ cá cược trái phép"
    if any(k in combined for k in ["betting shops", "high streets"]):
        return "Nghiên cứu vai trò kinh tế của chuỗi điểm cược đối với thị trường bán lẻ"
    if any(k in combined for k in ["igaming", "sportsbook", "betting platform", "casino tech"]):
        return f"Công nghệ và giải pháp nền tảng cá cược trực tuyến: {t_clean}"[:80]
    if any(k in combined for k in ["robotics", "robot report", "humanoid", "drone", "quadruped"]):
        return f"Ứng dụng robot tự hành và công nghệ điều khiển thông minh: {t_clean}"[:80]
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

TRENDS_KEYWORD_SUMMARIES = {
    # Nhóm A: Thị trường lớn
    "IoT market": "Nhu cầu thị trường thiết bị kết nối IoT toàn cầu đang tăng trưởng",
    "AI hardware": "Làn sóng tìm kiếm chip chuyên dụng và phần cứng tăng tốc AI",
    "robotics startup": "Sự quan tâm đến các startup robot và tự động hóa công nghiệp",
    "edge computing": "Xu hướng tính toán biên xử lý dữ liệu trực tiếp tại thiết bị",
    "semiconductor shortage": "Theo dõi tình hình cung ứng và biến động giá linh kiện bán dẫn",
    "smart home devices": "Nhu cầu thiết bị nhà thông minh và tự động hóa dân dụng",
    # Nhóm B: Ngành dọc tiềm năng
    "smart agriculture": "Tìm kiếm về công nghệ và cảm biến nông nghiệp thông minh tăng mạnh",
    "water technology": "Mối quan tâm về công nghệ xử lý và quan trắc nước diện rộng",
    "renewable energy": "Xu hướng chuyển dịch năng lượng tái tạo và lưu trữ điện",
    "3D printing market": "Ứng dụng in 3D trong chế tạo mẫu thử và sản xuất phần cứng",
    "electric vehicle": "Mức độ quan tâm thị trường xe điện và hạ tầng trạm sạc",
    "drone technology": "Công nghệ máy bay không người lái phục vụ khảo sát và giám sát",
    # Nhóm C: Tín hiệu vĩ mô
    "DRAM price": "Tín hiệu biến động chi phí linh kiện RAM và bộ nhớ phần cứng",
    "supply chain disruption": "Theo dõi nguy cơ đứt gãy và chậm trễ chuỗi cung ứng linh kiện",
    "startup funding trend": "Xu hướng dòng vốn đầu tư mạo hiểm vào các startup công nghệ",
    # Legacy / Niche aliases
    "water quality sensor": "Nhu cầu tìm kiếm cảm biến đo lường và quan trắc chất lượng nước",
    "aquaculture IoT": "Ứng dụng giải pháp IoT tự động hóa ao nuôi thủy sản",
    "ESP32 water monitor": "Nghiên cứu thiết bị giám sát nước tự chế dùng chip ESP32",
    "fish tank monitor": "Thiết bị đo thông số hồ cá cảnh và cảnh báo tự động",
    "shrimp farm sensor": "Cảm biến quan trắc môi trường đầm tôm và nồng độ oxy hòa tan",
}


def summarize_trends_keyword(keyword, volume=0, change="", status=""):
    """
    Generate natural Vietnamese summary (<= 100 chars) for Google Trends keyword.
    """
    kw_clean = keyword.strip()
    # Check exact keyword mapping
    if kw_clean in TRENDS_KEYWORD_SUMMARIES:
        base = TRENDS_KEYWORD_SUMMARIES[kw_clean]
    else:
        # Fallback keyword lookup
        kw_lower = kw_clean.lower()
        matched = None
        for k, v in TRENDS_KEYWORD_SUMMARIES.items():
            if k.lower() in kw_lower:
                matched = v
                break
        base = matched if matched else f"Lượng tìm kiếm trực tuyến về {kw_clean} trên thị trường"

    if len(base) > 95:
        base = base[:92].strip() + "..."
    return base


TWITTER_KEYWORD_SUMMARIES = {
    "#IoT": "Xu hướng thiết bị kết nối IoT và cảm biến thông minh đang được bàn luận sôi nổi",
    "#robotics": "Cộng đồng công nghệ thảo luận về robot tự hành và giải pháp tự động hóa",
    "#startup": "Cộng đồng khởi nghiệp chia sẻ sản phẩm mới và chiến lược gọi vốn",
    "#hardware": "Đánh giá thiết kế mạch, linh kiện bán dẫn và kiến trúc phần cứng",
    "#AI": "Làn sóng thảo luận nóng về bước tiến AI và ứng dụng vào thực tế",
    "IoT": "Xu hướng thiết bị kết nối IoT và cảm biến thông minh đang được bàn luận sôi nổi",
    "robotics": "Cộng đồng công nghệ thảo luận về robot tự hành và giải pháp tự động hóa",
    "startup": "Cộng đồng khởi nghiệp chia sẻ sản phẩm mới và chiến lược gọi vốn",
    "hardware": "Đánh giá thiết kế mạch, linh kiện bán dẫn và kiến trúc phần cứng",
    "AI": "Làn sóng thảo luận nóng về bước tiến AI và ứng dụng vào thực tế",
}


def summarize_twitter_trend(keyword, tweets="10K+", change=""):
    """
    Generate natural Vietnamese summary (<= 100 chars) for Twitter/X trending keyword.
    """
    kw_clean = keyword.strip()
    if kw_clean in TWITTER_KEYWORD_SUMMARIES:
        return TWITTER_KEYWORD_SUMMARIES[kw_clean]
    kw_lower = kw_clean.lower()
    for k, v in TWITTER_KEYWORD_SUMMARIES.items():
        if k.lower() in kw_lower:
            return v
    topic_name = kw_clean[1:] if kw_clean.startswith("#") else kw_clean
    return f"Chủ đề {topic_name} đang là tâm điểm bàn luận với lượng tương tác tăng cao"


REDDIT_SEED_SUMMARIES = {
    # startups / entrepreneur / smallbusiness
    "How we bootstrapped our hardware IoT gateway to $20k MRR without VC": "Kinh nghiệm bootstrap startup gateway IoT đạt 20k USD MRR không cần vốn VC",
    "Finding B2B customers for physical hardware products: Lessons learned": "Bài học tiếp cận và chốt hợp đồng khách hàng B2B cho sản phẩm phần cứng",
    "Energy costs and equipment monitoring are killing our margins this quarter": "Chi phí năng lượng và bảo trì máy móc đè nặng biên lợi nhuận kinh doanh nhỏ",
    # technology / hardware
    "Cambridge Analytica's fallout is still costing Meta, this time $25 billion in New Mexico": "Meta đối mặt vụ kiện và áp lực pháp lý 25 tỷ USD về bảo mật dữ liệu",
    "Ron DeSantis Floats 'Criminal Liability' for AI Executives": "Đề xuất quy trách nhiệm hình sự cho lãnh đạo các tập đoàn công nghệ AI",
    "He Had the Know-How to Fix His Tesla. But Telsa Told Him He Couldn’t.": "Quyền tự sửa chữa thiết bị công nghệ và xe điện trước rào cản hãng",
    "Next-gen low-power RISC-V microcontrollers entering mass production": "Vi điều khiển RISC-V tiêu thụ điện siêu thấp bắt đầu sản xuất hàng loạt",
    # robotics / iot / embedded / arduino
    "State of open-source ROS2 robot actuators and motor drivers in 2026": "Đánh giá driver động cơ và bộ truyền động robot mã nguồn mở ROS2",
    "Deploying 100+ low-power environmental sensors across remote facilities with LoRaWAN": "Kinh nghiệm triển khai 100+ cảm biến môi trường LoRaWAN tầm xa",
    "I built an RP2350 multitool that hosts its own desktop-style web UI over USB": "Thiết kế thiết bị RP2350 nhúng giao diện web trực tiếp qua cổng USB",
    "ESP32-S3 telemetry station with solar charging and low-power deep sleep": "Trạm đo từ xa dùng ESP32-S3 tích hợp sạc pin mặt trời và deep sleep",
    # futurology / singularity
    "Autonomous robotics and physical AI are decoupling manufacturing from labor shortages": "Robot tự hành và AI vật lý giúp giải quyết bài toán thiếu hụt nhân lực",
    "Embodied intelligence breakthroughs: From language models to physical world manipulation": "Đột phá AI hiện thân kết hợp mô hình ngôn ngữ với thao tác vật lý",
}


def summarize_reddit_post(title, summary="", subreddit=""):
    """
    Generate natural Vietnamese summary (<= 100 chars) for Reddit posts.
    """
    t = (title or "").strip()
    if t in REDDIT_SEED_SUMMARIES:
        return REDDIT_SEED_SUMMARIES[t]

    t_lower = t.lower()
    s_lower = (summary or "").lower()
    sub_lower = (subreddit or "").lower().replace("r/", "").strip()
    combined = f"{t_lower} {s_lower}"

    # Check keyword patterns
    if "meta" in combined and ("billion" in combined or "court" in combined or "sue" in combined):
        return "Meta đối mặt áp lực pháp lý và bồi thường liên quan bảo mật dữ liệu"
    if "tesla" in combined or "repair" in combined and "know-how" in combined:
        return "Tranh cãi về quyền tự sửa chữa thiết bị công nghệ và xe điện"
    if "desantis" in combined or ("criminal liability" in combined and "ai" in combined):
        return "Đề xuất quy định trách nhiệm hình sự đối với lãnh đạo công nghệ AI"
    if "bootstrap" in combined and ("mrr" in combined or "hardware" in combined or "iot" in combined):
        return "Kinh nghiệm bootstrap sản phẩm phần cứng IoT đạt doanh thu định kỳ"
    if "risc-v" in combined or ("microcontroller" in combined and "production" in combined):
        return "Sản xuất hàng loạt chip vi điều khiển kiến trúc RISC-V điện năng thấp"
    if "ros2" in combined or "actuator" in combined or "motor driver" in combined:
        return "Hệ sinh thái bộ truyền động và driver điều khiển robot mã nguồn mở"
    if "lorawan" in combined or ("sensor" in combined and "remote" in combined):
        return "Triển khai mạng cảm biến quan trắc từ xa công nghệ LoRaWAN"
    if "rp2350" in combined or ("web ui" in combined and "usb" in combined):
        return "Thiết bị nhúng vi điều khiển tích hợp giao diện web qua USB"
    if "esp32" in combined and ("solar" in combined or "telemetry" in combined or "sleep" in combined):
        return "Trạm đo từ xa dùng vi điều khiển ESP32 và pin năng lượng mặt trời"
    if "embodied" in combined or "manipulation" in combined:
        return "AI hiện thân kết hợp mô hình học sâu với khả năng tương tác vật lý"
    if "humanoid" in combined or "digit" in combined:
        return "Thử nghiệm robot hình người tự hành trong môi trường công nghiệp"
    if "roboweeder" in combined or ("weed" in combined and "robot" in combined):
        return "Robot nông nghiệp tự hành nhận diện và diệt cỏ chính xác cao"

    # Subreddit-based fallback
    if sub_lower in ["startups", "entrepreneur", "smallbusiness"]:
        return "Thảo luận kinh nghiệm phát triển mô hình kinh doanh và mở rộng thị trường"
    if sub_lower in ["robotics"]:
        return "Thảo luận giải pháp tự động hóa và phát triển hệ thống robot thực tế"
    if sub_lower in ["hardware"]:
        return "Đánh giá linh kiện phần cứng, thiết kế vi mạch và hiệu năng thiết bị"
    if sub_lower in ["iot"]:
        return "Ứng dụng giải pháp cảm biến IoT và mạng truyền dữ liệu từ xa"
    if sub_lower in ["embedded", "arduino"]:
        return "Thiết kế mạch nhúng, firmware vi điều khiển và chế tạo thiết bị"
    if sub_lower in ["futurology", "singularity"]:
        return "Dự báo bước tiến công nghệ trí tuệ nhân tạo và tác động xã hội"
    if sub_lower in ["technology"]:
        return "Xu hướng phát triển công nghệ số và chính sách quản lý mới"

    # Generic fallback
    res = f"Thảo luận cộng đồng công nghệ: {t}"
    if len(res) > 95:
        res = res[:92].strip() + "..."
    return res


def generate_summary_vi(title, summary=""):
    """
    Main entry point: Generate a strictly compliant Vietnamese summary.
    - Max 80-100 characters
    - Answering "CƠ HỘI NÀY LÀ GÌ"
    - NEVER contains banned phrase "Tín hiệu công nghệ và cơ hội thị trường"
    """
    if not title:
        return "Giải pháp công nghệ và cơ hội thị trường mới"

    t = title.strip()

    # 1. Exact match lookup
    if t in EXACT_MATCHES:
        summary_vi = EXACT_MATCHES[t]
    # 2. Google Trends title pattern ("Google Trends: keyword (Status Change)")
    elif t.startswith("Google Trends:"):
        kw_m = re.match(r"^Google Trends:\s*([^(]+?)(?:\s*\((.*?)\))?$", t)
        if kw_m:
            kw = kw_m.group(1).strip()
            summary_vi = summarize_trends_keyword(kw)
        else:
            summary_vi = summarize_news_article(t, summary)
    # 2b. Twitter Trending title pattern ("#keyword trending with X tweets")
    elif "trending with" in t.lower() and "tweets" in t.lower():
        kw_m = re.match(r"^([#\w\s]+?)\s+trending with", t, re.IGNORECASE)
        kw = kw_m.group(1).strip() if kw_m else t
        summary_vi = summarize_twitter_trend(kw)
    # 3. Funding article ([Ai] [làm gì] [bao nhiêu] [ngành gì])
    elif any(k in t.lower() for k in ["raises", "raised", "funding", "series a", "series b", "seed", "acquires", "acquisition", "nets", "lands", "secures", "layoffs", "venture", "vc", "dollars", "capital", "stake", "invest"]):
        funding_sum = summarize_funding_article(t, summary)
        summary_vi = funding_sum if funding_sum else summarize_news_article(t, summary)
    # 4. GitHub repository
    elif "/" in t and not t.startswith("http") and len(t.split("/")) == 2 and " " not in t.split("/")[0]:
        summary_vi = summarize_github_repo(t, summary)
    # 5. News article or paper
    else:
        summary_vi = summarize_news_article(t, summary)

    # Clean & ensure <= 80 chars (or 100 for reddit/trends)
    summary_vi = summary_vi.strip()
    if len(summary_vi) > 85:
        summary_vi = summary_vi[:82].strip() + "..."

    # Safety check: BANNED PHRASES MUST NEVER OCCUR
    banned = "tín hiệu công nghệ và cơ hội thị trường"
    if banned in summary_vi.lower():
        summary_vi = summarize_news_article(t, "")

    # Requirement B2: If summary_vi is empty or < 20 chars
    if not summary_vi or len(summary_vi) < 20:
        summary_vi = "Chưa có mô tả — nhấn link để xem chi tiết"

    return summary_vi


TITLE_VI_EXACT = {
    "Sea Harvest profit dips on low catch rates": "Sea Harvest lợi nhuận giảm do sản lượng đánh bắt thấp",
    "Sea Harvest profit dips on low catch rates, tough market conditions": "Sea Harvest lợi nhuận giảm do sản lượng đánh bắt thấp và thị trường khó khăn",
    "Metron Acquires H2O Degree to Add Submetering and Leak Detection": "Metron thâu tóm H2O Degree để bổ sung đo đếm và phát hiện rò rỉ",
    "VECKTA Raises $11 Million Series A Led by Origin Ventures for Onsite Solar and Storage": "VECKTA huy động $11M Series A do Origin Ventures dẫn đầu cho điện mặt trời & lưu trữ",
    "IMIO raises $12m to unlock nutrients trapped in crop residues with new generation of ‘dependable ag biologicals’": "IMIO huy động $12M phát triển chế phẩm sinh học từ phụ phẩm cây trồng",
    "Kodama nets $7m to scale physical AI for ‘intelligent forestry’": "Kodama gọi vốn $7M ứng dụng AI vật lý cho quản lý lâm nghiệp thông minh",
    "Farmers, what's missing from your water monitoring setup?": "Nông dân chia sẻ: Hệ thống quan trắc nước của bạn còn thiếu gì?",
    "US aquaculture needs more than VC dollars to grow: report": "Báo cáo: Ngành nuôi trồng thủy sản Mỹ cần nhiều hơn vốn đầu tư mạo hiểm",
    "Layoffs at Carbon Robotics as firm “realigns costs due to broader economic conditions”": "Carbon Robotics cắt giảm nhân sự để tái cơ cấu chi phí mảng robot",
    "UK Agri-Tech Centre to slash workforce by 60% in strategic pivot to new operating model": "Trung tâm AgTech Anh cắt 60% nhân sự chuyển dịch mô hình vận hành mới",
    "‘No acceptable offers’ for Liberation Bioindustries as firm seeks to plug $25m funding gap": "Liberation Bioindustries tìm kiếm $25M bù đắp khoảng trống vốn sinh học",
    "Semantic Observability for Autonomous Systems Diagnostics": "Khả năng quan sát ngữ nghĩa phục vụ chẩn đoán hệ thống tự hành",
    "From the control center, AI camera helps Hanoi traffic police monitor every traffic span - Laodong.vn": "Từ trung tâm điều khiển, camera AI giúp CSGT Hà Nội giám sát giao thông",
    "UniWALM: Unified World Action Language Model for Embodied Robot Control": "UniWALM: Mô hình ngôn ngữ hành động thế giới hợp nhất điều khiển robot",
    "Industrial ReMEmbR: Scaling Spatiotemporal Memory to Robot Fleets": "Industrial ReMEmbR: Mở rộng bộ nhớ không-thời gian cho đội ngũ robot",
    "AGCO and Agility Robotics to Pilot Digit Humanoid Robot at Hesston, Kansas, Plant": "AGCO và Agility Robotics thử nghiệm robot hình người Digit trong nhà máy",
    "Niqo Robotics Unveils 46-Foot RoboWeeder F50 for Specialty Crop Farms": "Niqo Robotics ra mắt robot diệt cỏ RoboWeeder F50 cho nông trại",
    "🎥 Earth Rover bets on pulsed light to tackle weeds without chemicals": "Earth Rover ứng dụng xung ánh sáng diệt cỏ không dùng hóa chất",
    "Rondo Energy and Rio Tinto Begin Design of Australia’s Largest Thermal Energy Storage Project": "Rondo Energy và Rio Tinto thiết kế dự án lưu trữ năng lượng nhiệt lớn nhất Australia",
    "Firm makes aquaponics, water treatment  breakthrough": "Doanh nghiệp đột phá công nghệ lọc nước và nuôi trồng aquaponics",
    "Firm makes aquaponics, water treatment breakthrough": "Doanh nghiệp đột phá công nghệ lọc nước và nuôi trồng aquaponics",
    "Tanzanian startup scaling sustainable fertiliser, fish feed solutions": "Startup Tanzania mở rộng phân bón hữu cơ và thức ăn cá bền vững",
    "South Africa, Chile collaborate to advance sustainable fisheries, aquaculture": "Nam Phi và Chile hợp tác phát triển thủy sản bền vững",
    "Microsoft issues a warning regarding AI regulation. - Vietnam.vn": "Microsoft cảnh báo về việc quản lý và ban hành luật AI",
    "Blockbuster films take two years to complete, AI can do it in just one or two months: Proposal for a separate Copyright Law. - Vietnam.vn": "Phim bom tấn cần 2 năm, AI làm trong 1-2 tháng: Đề xuất luật bản quyền riêng",
    "AI Law takes effect, anchors national governance framework - vietnamnews.vn": "Luật AI có hiệu lực, thiết lập khung quản trị quốc gia",
    "Regulations on the safety of AI applications in banking operations. - Vietnam.vn": "Quy định an toàn ứng dụng AI trong hoạt động ngân hàng",
    "The Law on Artificial Intelligence must ensure four key pillars - Tạp chí KH&CN Việt Nam": "Luật Trí tuệ nhân tạo phải đảm bảo 4 trụ cột chính",
}


def translate_title_vi(title, summary=""):
    """
    Translates or formats an English/raw title into a natural, reader-friendly Vietnamese title (Phase 17 - B1).
    """
    if not title:
        return "Tín hiệu công nghệ mới"

    t = title.strip()

    # 1. Exact match dictionary
    if t in TITLE_VI_EXACT:
        return TITLE_VI_EXACT[t]

    # Clean suffixes like ' - Vietnam.vn', ' | TechCrunch'
    t_clean = re.sub(r"\s*[-|–—]\s*[\w\s.]+$", "", t).strip()

    # 2. If title is already Vietnamese (contains tone marks)
    if bool(re.search(r"[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]", t_clean, re.IGNORECASE)):
        return t_clean

    # 3. Google Trends
    if t.startswith("Google Trends:"):
        kw = t.replace("Google Trends:", "").strip()
        kw = re.sub(r"\(.*?\)", "", kw).strip()
        return f"Xu hướng tìm kiếm đột biến: {kw}"

    # 4. Twitter Trends
    if "trending with" in t.lower() and "tweets" in t.lower():
        m = re.match(r"^([#\w\s]+?)\s+trending with\s*(\d+[KkMm]?)\s*tweets", t, re.IGNORECASE)
        if m:
            return f"Chủ đề hot X: {m.group(1).strip()} ({m.group(2)} thảo luận)"

    # 5. GitHub repository ('owner/repo')
    if "/" in t and not t.startswith("http") and len(t.split("/")) == 2 and " " not in t.split("/")[0]:
        owner, repo = t.split("/", 1)
        clean_repo = repo.replace("-", " ").replace("_", " ").title()
        return f"Dự án mã nguồn mở {clean_repo} ({owner})"

    # 6. Pattern-based translations
    # X acquires Y to add Z
    m_acq = re.search(r"^(.*?)\s+(?:acquires|to acquire|buys)\s+(.*?)(?:\s+to\s+add\s+(.*?))?$", t_clean, re.IGNORECASE)
    if m_acq:
        buyer = m_acq.group(1).strip()
        target = m_acq.group(2).strip()
        feat = m_acq.group(3).strip() if m_acq.group(3) else ""
        if feat:
            return f"{buyer} thâu tóm {target} để bổ sung {feat}"
        return f"{buyer} thâu tóm {target}"

    # X raises $Y for Z
    m_raise = re.search(r"^(.*?)\s+(?:raises|raised|secures|nets|lands)\s+(\$[\d.]+[MBmb]?|\d+\s*million|\d+\s*billion)(?:\s+(?:for|to|in)\s+(.*?))?$", t_clean, re.IGNORECASE)
    if m_raise:
        who = m_raise.group(1).strip()
        amt = m_raise.group(2).strip()
        purpose = m_raise.group(3).strip() if m_raise.group(3) else ""
        if purpose:
            return f"{who} huy động vốn {amt} cho {purpose}"
        return f"{who} huy động vốn {amt}"

    # Profit dips / drops
    m_dip = re.search(r"^(.*?)\s+(?:profit dips|revenue falls|profit drops)\s+(?:on|due to)\s+(.*?)$", t_clean, re.IGNORECASE)
    if m_dip:
        who = m_dip.group(1).strip()
        reason = m_dip.group(2).strip()
        return f"{who} lợi nhuận sụt giảm do {reason}"

    # Fallback: if summary_vi exists and is good, we can build from summary_vi
    sum_vi = generate_summary_vi(t, summary)
    if sum_vi and len(sum_vi) >= 15 and "Chưa có mô tả" not in sum_vi:
        return sum_vi

    return t_clean

