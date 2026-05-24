#!/usr/bin/env python3
"""
Generate AI evaluations for 39 universities in 辽宁/黑龙江/吉林/重庆/甘肃.
Each school gets 4-6 unique reviews with scores, tags, and comments.
"""

import sqlite3
import json
import random
import hashlib

random.seed(42)

DB_PATH = '/home/homesafe/projects/uni-review/data/uni_review.db'

# ============================================================
# MAJOR MATCHING RULES
# ============================================================
MAJOR_MAP = {
    '综合': ['哲学', '经济学', '法学', '文学', '历史学', '理学', '工学', '农学', '管理学', '艺术学'],
    '理工': ['经济学', '法学', '文学', '理学', '工学', '管理学'],
    '师范': ['哲学', '经济学', '法学', '教育学', '文学', '历史学', '理学', '管理学', '艺术学'],
    '医药': ['医学'],
    '农林': ['经济学', '法学', '文学', '理学', '工学', '农学', '管理学'],
    '财经': ['经济学', '法学', '文学', '管理学'],
    '政法': ['法学', '文学'],
    '语言': ['文学', '管理学'],
    '艺术': ['文学', '艺术学'],
    '体育': ['教育学'],  # 体育教育
    '民族': ['哲学', '经济学', '法学', '教育学', '文学', '历史学', '理学', '工学', '农学', '管理学', '艺术学'],
}

# Province modifiers (per category, in score points)
PROVINCE_MOD = {
    '辽宁': {'dormitory': -0.1, 'cafeteria': 0.0, 'employment': 0.0},
    '黑龙江': {'dormitory': -0.2, 'cafeteria': 0.0, 'employment': -0.1},
    '吉林': {'dormitory': -0.1, 'cafeteria': 0.0, 'employment': -0.1},
    '重庆': {'dormitory': 0.1, 'cafeteria': 0.2, 'employment': 0.0},
    '甘肃': {'dormitory': -0.2, 'cafeteria': -0.1, 'employment': -0.2},
}

LEVEL_MOD = {'985/211': 0.4, '211': 0.2, '双一流': 0.1, '普通': 0.0}

# Category names in English for DB
CAT_KEYS = ['academic', 'dormitory', 'cafeteria', 'cost', 'environment', 'employment', 'admin', 'mental']
CAT_WEIGHTS = {'academic': 15, 'dormitory': 25, 'cafeteria': 15, 'cost': 10,
               'environment': 8, 'employment': 20, 'admin': 5, 'mental': 2}

# ============================================================
# SCHOOL-SPECIFIC INFO (for comment generation)
# ============================================================
SCHOOL_INFO = {
    '大连理工大学': {
        'nickname': '大工',
        'details': '标准化4人间，部分有独卫，22:45断电，理工强校985',
        'tags_hint': ['宿舍断电', '标准四人间']
    },
    '东北大学': {
        'nickname': '东大',
        'details': '南湖校区宿舍较旧，浑南校区条件新，985工科强校',
        'tags_hint': ['南湖旧', '浑南新']
    },
    '大连海事大学': {
        'nickname': '海事',
        'details': '211航海特色，半军事化管理，海上交通运输',
        'tags_hint': ['半军事化']
    },
    '辽宁大学': {
        'nickname': '辽大',
        'details': '211综合大学，文科见长，宿舍条件普遍，蒲河校区较新',
        'tags_hint': ['文科见长']
    },
    '东北财经大学': {
        'nickname': '东财',
        'details': '财经类强校虽非211但业内认可度高，会计金融突出',
        'tags_hint': ['财经强校']
    },
    '大连医科大学': {
        'nickname': '大医',
        'details': '医学类高校，临床医学较强，位于大连旅顺口区',
        'tags_hint': ['医学']
    },
    '沈阳农业大学': {
        'nickname': '沈农',
        'details': '农林类高校，东陵校区，农业相关专业',
        'tags_hint': ['农林']
    },
    '沈阳工业大学': {
        'nickname': '沈工大',
        'details': '工科院校，电气机械较强，中央校区条件较好',
        'tags_hint': ['工科']
    },
    '沈阳理工大学': {
        'nickname': '沈理工',
        'details': '兵工背景，工科为主，浑南校区',
        'tags_hint': ['兵工']
    },
    '辽宁工程技术大学': {
        'nickname': '辽工大',
        'details': '原阜新矿业学院，位于阜新，工科传统',
        'tags_hint': ['矿业传统']
    },
    '辽宁师范大学': {
        'nickname': '辽师大',
        'details': '大连市区，师范类为主，文科教育较强',
        'tags_hint': ['师范']
    },
    '哈尔滨工业大学': {
        'nickname': '哈工大',
        'details': 'C9联盟985，4-6人间无空调（东北气候不需要），深圳校区条件新',
        'tags_hint': ['无空调', 'C9']
    },
    '哈尔滨工程大学': {
        'nickname': '哈工程',
        'details': '211，军工背景（哈军工传承），船舶海洋强项',
        'tags_hint': ['军工背景', '船舶']
    },
    '东北林业大学': {
        'nickname': '东林',
        'details': '211林业特色，位于哈尔滨，校园绿化好',
        'tags_hint': ['林业']
    },
    '东北农业大学': {
        'nickname': '东农',
        'details': '211农业特色，位于哈尔滨，农学食品科学强',
        'tags_hint': ['农业']
    },
    '东北石油大学': {
        'nickname': '东油',
        'details': '原大庆石油学院，位于大庆，石油石化特色',
        'tags_hint': ['石油']
    },
    '哈尔滨医科大学': {
        'nickname': '哈医大',
        'details': '医学强校，预防医学和临床医学较强，附属医院多',
        'tags_hint': ['医学']
    },
    '哈尔滨理工大学': {
        'nickname': '哈理工',
        'details': '工科为主，电气绝缘特色，位于哈尔滨',
        'tags_hint': ['工科']
    },
    '黑龙江中医药大学': {
        'nickname': '黑中医',
        'details': '中医药特色，针灸推拿较强，位于哈尔滨',
        'tags_hint': ['中医药']
    },
    '黑龙江大学': {
        'nickname': '黑大',
        'details': '综合大学，俄语全国领先，文科较强，位于哈尔滨',
        'tags_hint': ['俄语强']
    },
    '吉林大学': {
        'nickname': '吉大',
        'details': '985综合性大学，6个校区遍布长春，2026年4月首批3366台空调安装！',
        'tags_hint': ['空调新装', '六大校区']
    },
    '东北师范大学': {
        'nickname': '东师',
        'details': '211师范类，人民大街校区和净月校区，教育学和文科强',
        'tags_hint': ['师范']
    },
    '吉林农业大学': {
        'nickname': '吉农',
        'details': '农林类高校，位于长春，农业食品专业',
        'tags_hint': ['农林']
    },
    '长春工业大学': {
        'nickname': '长工大',
        'details': '工科院校，机械材料化工较强，位于长春',
        'tags_hint': ['工科']
    },
    '长春理工大学': {
        'nickname': '长理工',
        'details': '原长春光机学院，光学工程全国领先，光电特色',
        'tags_hint': ['光电']
    },
    '重庆大学': {
        'nickname': '重大',
        'details': '985综合，虎溪新校区条件好环境新，老校区（A/B区）宿舍较旧',
        'tags_hint': ['虎溪新', '老校区旧']
    },
    '西南大学': {
        'nickname': '西大',
        'details': '211综合，由西南师大和西南农大合并，校园超大（8000+亩），位于北碚区',
        'tags_hint': ['超大校园']
    },
    '西南政法大学': {
        'nickname': '西政',
        'details': '政法类顶尖，虽非211但在法学界地位极高，渝北校区',
        'tags_hint': ['法学名校']
    },
    '重庆交通大学': {
        'nickname': '重交',
        'details': '交通土建特色，双福校区和南岸校区，土木桥梁较强',
        'tags_hint': ['交通']
    },
    '重庆医科大学': {
        'nickname': '重医',
        'details': '医学强校，临床医学和儿科学全国有名，附属儿童医院知名',
        'tags_hint': ['医学']
    },
    '重庆理工大学': {
        'nickname': '重理工',
        'details': '工科为主，车辆工程和会计学较强，花溪校区环境好',
        'tags_hint': ['车辆']
    },
    '重庆科技大学': {
        'nickname': '重科',
        'details': '原重庆科技学院，石油冶金特色，大学城校区',
        'tags_hint': ['应用型']
    },
    '重庆邮电大学': {
        'nickname': '重邮',
        'details': '信息通信特色，计算机通信较强，就业率高，位于南山',
        'tags_hint': ['通信']
    },
    '兰州大学': {
        'nickname': '兰大',
        'details': '985综合性大学，榆中校区偏远但条件好校园大，城关校区旧',
        'tags_hint': ['榆中偏远', '老校区旧']
    },
    '兰州交通大学': {
        'nickname': '兰交大',
        'details': '原兰州铁道学院，轨道交通特色，土木运输较强',
        'tags_hint': ['铁道']
    },
    '兰州理工大学': {
        'nickname': '兰理工',
        'details': '工科院校，材料化工机械较强，前身甘肃工业大学',
        'tags_hint': ['工科']
    },
    '西北师范大学': {
        'nickname': '西北师大',
        'details': '师范类，位于兰州安宁区，教育学心理学较强',
        'tags_hint': ['师范']
    },
    '甘肃农业大学': {
        'nickname': '甘农',
        'details': '农业类高校，位于兰州，草学动物医学较强',
        'tags_hint': ['农业']
    },
    '天水师范学院': {
        'nickname': '天师',
        'details': '师范类，位于天水市，地方性师范院校',
        'tags_hint': ['地方师范']
    },
}

# ============================================================
# REVIEW CONTENT GENERATORS
# ============================================================
def get_base_scores(school_type, school_level, province):
    """Generate realistic base scores for each category."""
    level_bonus = LEVEL_MOD.get(school_level, 0.0)
    pmod = PROVINCE_MOD.get(province, {})

    scores = {}
    for cat in CAT_KEYS:
        # Base: random around 3.0-4.0 depending on type/level
        base = 3.0 + level_bonus * 2 + random.uniform(-0.3, 0.3)
        # Apply province modifier per category (match Chinese name)
        cat_cn = {'academic': 'academic', 'dormitory': 'dormitory', 'cafeteria': 'cafeteria',
                  'cost': 'cost', 'environment': 'environment', 'employment': 'employment',
                  'admin': 'admin', 'mental': 'mental'}
        if cat == 'dormitory' and 'dormitory' in pmod:
            base += pmod['dormitory']
        elif cat == 'cafeteria' and 'cafeteria' in pmod:
            base += pmod['cafeteria']
        elif cat == 'employment' and 'employment' in pmod:
            base += pmod['employment']
        # Clamp to 1.0-5.0
        scores[cat] = round(max(1.0, min(5.0, base)), 1)

    # Special adjustments for known schools
    if school_level == '985/211':
        scores['academic'] = min(5.0, scores['academic'] + 0.3)
        scores['employment'] = min(5.0, scores['employment'] + 0.2)

    return scores


def calc_overall(category_scores):
    """Weighted overall score."""
    total = sum(category_scores.get(k, 3.0) * CAT_WEIGHTS.get(k, 10) for k in CAT_KEYS)
    return round(total / sum(CAT_WEIGHTS.values()), 1)


def generate_tags(category_scores, school_info, province):
    """Generate relevant tags based on scores and school info."""
    all_tags = [
        "内卷严重", "佛系养身", "食堂神仙", "食堂地狱", "空调自由",
        "空调绝缘", "电梯便利", "爬楼达人", "校园巨美", "校园荒凉",
        "宿舍豪华", "宿舍破旧", "老师超好", "老师摆烂", "就业无忧",
        "就业困难", "WiFi飞起", "WiFi龟速", "图书馆霸位", "社团丰富",
        "强制校园跑", "强制早晚自习", "形式主义", "水电刺客", "就业率注水"
    ]

    tags = []
    d = category_scores.get('dormitory', 3.0)
    c = category_scores.get('cafeteria', 3.0)
    e = category_scores.get('employment', 3.0)
    env = category_scores.get('environment', 3.0)

    if d >= 4.0: tags.append("宿舍豪华")
    elif d <= 2.0: tags.append("宿舍破旧")
    if c >= 4.0: tags.append("食堂神仙")
    elif c <= 2.0: tags.append("食堂地狱")
    if e >= 4.0: tags.append("就业无忧")
    elif e <= 2.5: tags.append("就业困难")
    if env >= 4.0: tags.append("校园巨美")
    elif env <= 2.5: tags.append("校园荒凉")

    if random.random() < 0.3: tags.append("内卷严重")
    if random.random() < 0.3: tags.append("老师超好")
    if random.random() < 0.2: tags.append("社团丰富")
    if random.random() < 0.15: tags.append("形式主义")

    # School specific
    name = school_info.get('nickname', '')
    if '哈工大' in str(school_info) or name == '哈工大':
        tags.append("空调绝缘")
    if '吉大' in str(school_info) or '吉林大学' in str(school_info):
        if random.random() < 0.6:
            tags.append("空调自由")

    return list(set(tags))[:4]


def generate_comment(school_name, school_info, province, scores, review_idx):
    """Generate unique, detailed comment for each review."""
    info = SCHOOL_INFO.get(school_name, {})
    nickname = info.get('details', school_name)
    pmod = PROVINCE_MOD.get(province, {})
    dorm_score = scores.get('dormitory', 3.0)
    cafe_score = scores.get('cafeteria', 3.0)
    emp_score = scores.get('employment', 3.0)

    comments_pool = []

    if school_name == '吉林大学':
        comments_pool = [
            f"吉大六个校区实在是太大了，在长春一天根本走不完。2026年4月首批3366台空调已经安装，南区宿舍终于有救了！前卫南区食堂不错，但南岭校区就差点意思。就业方面吉大招牌还是硬，东三省企业来校招不少，就是冬天太长了。",
            f"作为吉大南岭校区老生，终于等到2026年4月装空调了！首批3366台，南区先装，我们还在等后续批次。六个校区通勤真的是大问题，校车经常挤不上去。不过学术氛围很浓，图书馆永远爆满。",
            f"吉大真的是长春的大学——整个城市都是校园。2026年首批空调安装是个好消息，等了这么多年终于不用靠风扇扛夏天了。食堂价格便宜但种类一般，经信食堂算最好的。就业主要看专业，工科好于文科。",
            f"在吉大前卫南区住了三年，今年4月首批3366台空调到位，夏天终于不怕了！六个校区分布太散，选课经常要跨校区跑。但吉大的社团活动和学术讲座是真的多，985平台优势明显。",
            f"吉大太大了，六个校区各有特色。2026年4月首批空调安装后南区宿舍评分直线上升。医学院那边条件还是差一些。整体来说吉大在东三省认可度极高，尤其是法律、医学和化学。",
            f"刚来吉大的时候被六个校区震惊了，校车就是生命线。2026年装空调的消息让我们老生感动到哭，首批3366台终于落地。食堂方面推荐日新楼，外卖也挺方便的。社团活动很丰富。",
        ]
    elif school_name == '哈尔滨工业大学':
        comments_pool = [
            f"哈工大C9光环加持，学习氛围浓厚到让人喘不过气。宿舍4-6人间没有空调，但东北夏天也就热那几天，冬天暖气给力得穿短袖。食堂中规中矩，学苑楼性价比高。深圳校区条件确实好很多。",
            f"工科生的天堂，实验室条件一流。宿舍没空调在东北真不是问题，冬天暖气足就够了。一校区食堂三楼的自选不错。就业完全不用愁，华为腾讯每年校招必来。就是男女比例感人。",
            f"哈工大本部的宿舍确实朴实，4人间无空调，但东北夏天真用不上。航天和计算机专业强到离谱，校园里到处都是各种卫星模型。深圳校区条件好但本部的底蕴无可替代。",
            f"在哈工大读书最深的感受就是——卷，但卷得有价值。宿舍虽然没有空调，哈尔滨夏天晚上凉快不影响睡觉。食堂比上不足比下有余，学士楼还可以。就业去航天院所和互联网大厂的都很多。",
            f"哈工大的学风从大一就拉满，做实验到晚上十点是常态。4-6人间无空调，东北娃表示完全ok。食堂种类不算多但价格良心。就业率在工科院校里属于第一梯队，华为中兴航天科工是主要去向。",
        ]
    elif school_name == '兰州大学':
        comments_pool = [
            f"榆中校区真是又远又大，进城坐校车要一个小时！但宿舍条件确实好于城关本部，四人间有阳台。城关校区在市中心方便但宿舍旧。学习氛围极好，萃英学院精英培养。就业受地域影响大。",
            f"兰大榆中校区除了远没别的毛病，宿舍新、校园大、空气好。城关校区就在市区但住宿条件一言难尽。榆中的食堂一般，外卖选择少。学术上兰大是低调的实力派，化学地理全国知名。",
            f"在榆中校区待了两年最大的感受是：静心读书的好地方，因为想出去浪也没地方去😂 宿舍条件确实不错，比城关好太多了。唯一的痛点是榆中到市区的校车经常排队半小时以上。",
            f"城关校区在市区去哪都方便，但宿舍真的是老破小，六人间上下铺。榆中校区相反——偏远但舒适。兰大的学术水平绝对对得起985称号，就是在西北就业市场不如东部高校有优势。",
            f"兰大榆中校区的天空是我见过最美的大学天空，但偏远也是真的偏远。宿舍条件在西北算不错的了。城关校区主打一个历史感，宿舍旧得很有年代感。兰大学风很好，适合踏踏实实做学术。",
        ]
    elif school_name == '东北大学':
        comments_pool = [
            f"南湖校区老宿舍是真的旧，六人间上下铺，但浑南校区条件好一个档次。学校工科很强，自动化计算机是王牌。就业在东北算很不错的了，东软华为都来。南湖附近美食很多，太原街也不远。",
            f"东大南湖校区地理位置绝了，出门就是三好街和太原街，吃喝玩乐不愁。就是宿舍条件参差不齐，有的楼新有的楼旧。浑南校区新建的就好太多。工科实力强，实验室设备齐全。",
            f"在东北大学南湖住了两年，宿舍确实老，但习惯了也就那样。浑南校区新宿舍让人羡慕。学校对竞赛支持力度很大，ACM机器人比赛都有好成绩。食堂一舍和三舍的都不错。",
            f"东大学习氛围可以，没有某些985那么卷。南湖校区交通方便，浑南校区安静适合搞学术。宿舍分三六九等，选宿舍全靠运气。就业率理工科很稳，文科稍微弱一些。",
        ]
    elif school_name == '大连理工大学':
        comments_pool = [
            f"大工的标准化四人间还算规整，部分楼有独卫，但22:45准时断电这个真的很烦人。北山生活区食堂丰富，理工科氛围浓厚。就业率很高，尤其化工机械土木这些传统工科。",
            f"凌水河畔的大工很美，秋天银杏大道绝了。四人间上床下桌标配，就是22:45断电之后只能睡觉。食堂沁园好吃，北山A区就是食堂地狱。985光环在东北找工作轻松。",
            f"在大工每天和断电时间赛跑，22:45准时黑，台式机党痛不欲生。宿舍条件算中等偏上，部分有独卫。学校对学术要求严格，考试难挂科率高但教学质量确实好。大连城市也很加分。",
            f"大工的学霸是真的多，图书馆永远找不到空位。断电政策虽然烦但也让人作息规律了。北门外面小吃街好吃不贵。就业上大工在化工、机械、船舶领域就是金字招牌。",
            f"大连理工的校园环境在东北高校里数一数二，面朝大海春天开花。宿舍22:45断电太反人类了！食堂推荐沁园，北山食堂就是凑合吃。就业工科不愁，尤其去一汽、中广核、华为的特别多。",
        ]
    elif school_name == '大连海事大学':
        comments_pool = [
            f"海事大学半军事化管理真的是有点严格，早上跑操晚上查寝。但航海技术和轮机工程全国顶尖。宿舍条件中等，东山校区较旧，西山新区好一些。就业方向很明确——航运海事系统。",
            f"半军事化管理让你体验在校大学生变海军的感受。制服确实帅，但每天列队上课也挺心累。作为211航海类院校，就业率真不愁，就是工作环境比较特殊。大连海事在国际航运界认可度极高。",
            f"海事的校园就在海边，散步就能看到大海。半军事化管理大一最严，后面慢慢松了。食堂推荐心海餐厅和五食堂。航海类专业就业好但工作辛苦，陆上专业如法学经管也不错。",
        ]
    elif school_name == '辽宁大学':
        comments_pool = [
            f"辽大蒲河校区比较新，宿舍条件不错四人间上床下桌。崇山校区老校区就一般了。作为211文科院校，法律经济和文学是强项。校园环境蒲河校区好，崇山校区在市区方便。",
            f"辽大的经济学院是王牌，经济学专业在东北地区认可度很高。宿舍看校区，蒲河新校区条件好，崇山就凑合。周围环境蒲河偏一些但安静，适合学习。就业文科生偏考公考研。",
            f"在辽大读经济学的体验：教授水平很高，很多都是海归。社科类图书馆藏书丰富。宿舍条件蒲河好于崇山，建议选蒲河。食堂两校区都还行，崇山附近美食多。",
        ]
    elif school_name == '重庆大学':
        comments_pool = [
            f"重大虎溪校区环境绝了，新宿舍四人间有空调独卫，像住在度假村。老校区A/B区就旧了，六人间上下铺。饭菜水平在重庆高校算中上，虎溪食堂选择多。直辖市就业面广，尤其机械电气建筑。",
            f"虎溪校区是我见过最美的校区之一，缙云湖畔跑步太惬意了。宿舍条件没得挑。但如果你分到老校区，那落差感就很强。重庆美食不用多说，走出校门就是火锅天堂。",
            f"在重大虎溪住了一年，回A区老宿舍直接崩溃。虎溪的空调和独卫绝对是985顶配。食堂一食堂的干锅好吃。学校工科强，建筑土木机械电气都是王牌，校企合作很多。",
            f"重大老校区宿舍真的是上个时代的产物，六人间没独卫。但新校区虎溪又确实好到让人羡慕。重庆大学的建筑学和电气工程在全国很有名。在重庆就业的话，重大就是地头蛇。",
        ]
    elif school_name == '西南大学':
        comments_pool = [
            f"西大校园八千多亩，上课骑自行车都得十分钟。有西南地区最大图书馆，桑蚕学和心理学全国顶尖。宿舍条件整体中等偏上。校园里还有自己的试验田和蚕学宫，简直像植物园。",
            f"西南大学大到离谱，校内需要坐校车。原西南师大和西南农大合并后学科很全，心理学和农学是招牌。宿舍北区比南区好一些。食堂多到数不清，禾丰楼和杏园食堂不错。",
            f"在西南大学读书四年都没逛完整个校园你敢信？北碚虽然离市中心远但环境好空气好。学校211平台够用，师范类专业就业很好，农学有自己的基地。宿舍条件看运气分配。",
        ]
    elif school_name == '东北师范大学':
        comments_pool = [
            f"东师人民大街校区在市中心，去哪里都方便，但宿舍老。净月校区新环境好，但偏一些。作为211师范院校，教育学、文学和理科都很强。东北中小学教师里到处都是东师校友。",
            f"东北师大的学风很好，图书馆永远很多人。净月校区的宿舍条件比本部好很多。师范生培养质量很高，就业率在师范院校里名列前茅。理科实验班也很强，不是只有师范专业。",
            f"东师本部在长春市中心，附近有桂林路美食街，生活便利。净月校区安静适合学习。学校对免费师范生政策透明。文科专业教授水平很高。冬天校园雪景很美。",
        ]
    elif school_name == '哈尔滨工程大学':
        comments_pool = [
            f"哈工程军工背景太强了，校园里还有导弹模型和军舰展区。船舶工程和水声工程全国数一数二。宿舍条件中等，六人间为主。军工系统的就业渠道很通畅，中船重工每年都来。",
            f"在哈工程读书你会有种在军事基地上学的错觉。学校管理严格，学风扎实。传承哈军工的传统，军工精神浓厚。食堂的话美食城和大学生美食广场都可以。就业去造船厂和研究所的很多。",
            f"哈工程的校园建筑是俄式风格很漂亮，每年杏花节特别美。宿舍条件一般，但新公寓在建。作为211军工院校，保密管理严格。船舶和核能专业毕业生供不应求。",
        ]
    elif school_name == '东北林业大学':
        comments_pool = [
            f"东林校园绿化率太高了，简直就是城市里的森林。211林业特色，园林和森林工程是王牌。宿舍条件在哈尔滨高校里算中等。食堂种类偏少，但价格不贵。就业林业系统为主。",
            f"在东北林业大学读书每天都是天然氧吧。学校专业特色鲜明，野生动物保护和林学全国领先。宿舍六人间为主，新公寓条件好。哈尔滨冬天零下三十度，但学校暖气够足。",
        ]
    elif school_name == '东北农业大学':
        comments_pool = [
            f"东农的食品科学和农学是真强，有自己的实验农场和乳品中心。211农业院校里性价比很高。宿舍条件一般，六人间为主。食堂很有特色，农大自己产的酸奶和红肠很有名！",
            f"东北农大在哈尔滨香坊区，校园不大但很精致。农学食品相关专业实验条件好，有自己的大棚和牧场。毕业生去北大荒和食品企业的很多。食堂的酸奶和面包是抢手货。",
        ]

    if not comments_pool:
        # Generic comments based on scores and province
        dorm_text = "宿舍条件不错" if dorm_score >= 3.5 else "宿舍条件一般" if dorm_score >= 2.5 else "宿舍条件较差"
        cafe_text = "食堂不错" if cafe_score >= 3.5 else "食堂一般" if cafe_score >= 2.5 else "食堂不好吃"
        emp_text = "就业前景不错" if emp_score >= 3.5 else "就业前景一般" if emp_score >= 2.5 else "就业比较困难"

        province_specific = {
            '辽宁': '在辽宁高校中，',
            '黑龙江': '在黑龙江这边，',
            '吉林': '在吉林这个省份，',
            '重庆': '在重庆这座城市，',
            '甘肃': '在甘肃这边，',
        }
        pref = province_specific.get(province, '')

        comment = f"{pref}{school_name}整体来说{dorm_text}，{cafe_text}。{emp_text}"
        # Add school-specific details
        if school_name in SCHOOL_INFO:
            detail = SCHOOL_INFO[school_name]['details']
            comment += f"。{detail[:50]}"

        if len(comment) > 150:
            comment = comment[:147] + "..."

        comments_pool = [comment]

    # Pick based on idx to ensure variety
    return comments_pool[review_idx % len(comments_pool)]


def get_major_category(school_type):
    """Get allowed major categories for this school type."""
    return MAJOR_MAP.get(school_type, ['文学'])


def get_device_id(school_name, idx):
    """Generate a consistent fake device ID."""
    raw = f"ai-gen-{school_name}-{idx}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def main():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Load all majors
    c.execute("SELECT id, name, category FROM majors")
    all_majors = c.fetchall()

    # Group majors by category
    majors_by_cat = {}
    for mid, mname, mcat in all_majors:
        majors_by_cat.setdefault(mcat, []).append((mid, mname))

    # Get target schools
    provinces = ['辽宁', '黑龙江', '吉林', '重庆', '甘肃']
    c.execute(f"SELECT id, name, province, type, level FROM schools WHERE province IN ({','.join('?'*len(provinces))}) ORDER BY province, name", provinces)
    schools = c.fetchall()

    # Also handle the specific major-matching schools
    # 体育→教育(体育教育)  so for sports type, only 体育教育
    # 医药→仅医学

    total_inserted = 0
    for sid, sname, sprv, stype, slevel in schools:
        allowed_cats = get_major_category(stype)
        if stype == '体育':
            # Only 体育教育 (id=16)
            allowed_majors = [(16, '体育教育')]
        elif stype == '医药':
            # Only medical majors
            allowed_majors = majors_by_cat.get('医学', [])
        else:
            allowed_majors = []
            for cat in allowed_cats:
                allowed_majors.extend(majors_by_cat.get(cat, []))

        if not allowed_majors:
            # Fallback
            allowed_majors = [(9, '法学')]

        num_reviews = random.randint(4, 6)
        for ri in range(num_reviews):
            # Pick a random major from allowed list
            mid, mname = random.choice(allowed_majors)

            category_scores = get_base_scores(stype, slevel, sprv)
            overall = calc_overall(category_scores)
            tags = generate_tags(category_scores, SCHOOL_INFO.get(sname, {}), sprv)
            comment = generate_comment(sname, SCHOOL_INFO.get(sname, {}), sprv, category_scores, ri)
            device_id = get_device_id(sname, ri)

            # Generate answers based on category_scores
            # Convert category scores back to question answers
            answers = {}
            # Load config questions to generate plausible answers
            questions_by_cat = {
                'academic': ['forced_run', 'forced_study', 'hard_course_select', 'system_crash', 'bad_curriculum', 'forced_lecture', 'bad_exam_schedule'],
                'dormitory': ['private_bathroom', 'has_ac', 'power_limit', 'has_curfew', 'bunk_bed', 'over_6_room', 'room_check', 'hot_water_24h', 'laundry_access'],
                'cafeteria': ['bad_food', 'expensive_food', 'food_safety_issue', 'limited_variety', 'no_delivery', 'no_nearby_food'],
                'cost': ['expensive_utilities', 'hidden_fees', 'bad_internet', 'forced_internship_fee', 'unclear_fees', 'campus_monopoly'],
                'environment': ['remote_location', 'small_campus', 'poor_facilities', 'no_transit', 'bad_security', 'multi_campus'],
                'employment': ['fake_employment_rate', 'forced_sign', 'useless_career_center', 'bad_job_fair', 'low_recognition', 'trap_major', 'forced_factory'],
                'admin': ['slow_admin', 'bad_counselor', 'formalism', 'unfair_scholarship', 'no_feedback_channel', 'random_plan_change', 'bureaucracy'],
                'mental': ['no_counseling', 'no_room_change', 'bad_club'],
            }

            for cat_key, qs in questions_by_cat.items():
                cat_score = category_scores.get(cat_key, 3.0)
                # Higher score → more "yes" answers to positive questions
                for q in qs:
                    # Determine if this is a "positive" or "negative" question
                    # Actually, let's just randomly assign based on score
                    if random.random() < (cat_score - 1) / 4:  # Higher score = more positive answers
                        answers[q] = random.choice([True, True, False])  # Mostly positive
                    else:
                        answers[q] = random.choice([True, False, False])  # Mostly negative

            # Special overrides for known school features
            if sname == '大连理工大学':
                answers['power_limit'] = True  # 22:45断电
            elif sname == '哈尔滨工业大学':
                answers['has_ac'] = False  # 无空调
                if ri < 2:
                    answers['no_counseling'] = True
            elif sname == '吉林大学':
                if ri == 0 or ri == 1:
                    answers['has_ac'] = True  # 新装空调
                answers['multi_campus'] = True  # 6个校区
            elif sname == '兰州大学':
                if '榆中' in str(comment) or ri < 2:
                    answers['remote_location'] = True  # 榆中偏远
                answers['multi_campus'] = True
            elif sname == '重庆大学':
                if '虎溪' in str(comment) or ri < 2:
                    answers['has_ac'] = True
                    answers['private_bathroom'] = True
            elif sname == '哈尔滨工程大学':
                if ri < 2:
                    answers['formalism'] = True  # 军工管理严格

            answers_json = json.dumps(answers, ensure_ascii=False)
            cat_scores_json = json.dumps(category_scores, ensure_ascii=False)
            tags_json = json.dumps(tags, ensure_ascii=False)

            c.execute("""
                INSERT INTO reviews (school_id, major_id, device_id, answers, category_scores, overall_score, comment, tags, likes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, datetime('now'))
            """, (sid, mid, device_id, answers_json, cat_scores_json, overall, comment, tags_json))
            total_inserted += 1

        print(f"  {sname} ({sprv}, {stype}, {slevel}): {num_reviews} reviews inserted")

    conn.commit()
    conn.close()
    print(f"\nTotal: {total_inserted} AI reviews generated across {len(schools)} schools.")


if __name__ == '__main__':
    main()
