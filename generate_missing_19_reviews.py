#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为19所缺少评价的高校生成AI评价（3-4条/校）
省份: 安徽、山西、广东、江西、河北、河南、福建
"""
import sqlite3
import json
import random
import hashlib

random.seed(42)
DB_PATH = '/home/homesafe/projects/uni-review/data/uni_review.db'

# ============================================================
# 专业匹配规则
# ============================================================
MAJOR_MATCH = {
    '理工': ['经济学', '法学', '文学', '理学', '工学', '管理学'],
    '师范': ['哲学', '经济学', '法学', '教育学', '文学', '历史学', '理学', '管理学', '艺术学'],
    '医药': ['医学'],
    '综合': ['经济学', '法学', '文学', '理学', '工学', '农学', '医学', '管理学', '教育学', '历史学', '哲学', '艺术学'],
}

# Province adjustments (per category score bonus)
PROVINCE_ADJ = {
    '安徽': {'dormitory': 0.2, 'cafeteria': 0.1, 'employment': 0.1},
    '山西': {'dormitory': -0.1, 'cafeteria': 0.0, 'employment': -0.1},
    '广东': {'dormitory': 0.2, 'cafeteria': 0.2, 'employment': 0.2},
    '江西': {'dormitory': 0.0, 'cafeteria': 0.0, 'employment': 0.0},
    '河北': {'dormitory': 0.0, 'cafeteria': 0.0, 'employment': 0.0},
    '河南': {'dormitory': 0.0, 'cafeteria': 0.1, 'employment': 0.0},
    '福建': {'dormitory': 0.2, 'cafeteria': 0.1, 'employment': 0.1},
}

LEVEL_BONUS = {'985/211': 0.4, '985': 0.4, '211': 0.2, '双一流': 0.1, '普通': 0.0}

CAT_KEYS = ['academic', 'dormitory', 'cafeteria', 'cost', 'environment', 'employment', 'admin', 'mental']
CAT_WEIGHTS = {'academic': 15, 'dormitory': 25, 'cafeteria': 15, 'cost': 10,
               'environment': 8, 'employment': 20, 'admin': 5, 'mental': 2}

QUESTIONS_BY_CAT = {
    'academic': ['forced_run', 'forced_study', 'hard_course_select', 'system_crash', 'bad_curriculum', 'forced_lecture', 'bad_exam_schedule'],
    'dormitory': ['private_bathroom', 'has_ac', 'power_limit', 'has_curfew', 'bunk_bed', 'over_6_room', 'room_check', 'hot_water_24h', 'laundry_access'],
    'cafeteria': ['bad_food', 'expensive_food', 'food_safety_issue', 'limited_variety', 'no_delivery', 'no_nearby_food'],
    'cost': ['expensive_utilities', 'hidden_fees', 'bad_internet', 'forced_internship_fee', 'unclear_fees', 'campus_monopoly'],
    'environment': ['remote_location', 'small_campus', 'poor_facilities', 'no_transit', 'bad_security', 'multi_campus'],
    'employment': ['fake_employment_rate', 'forced_sign', 'useless_career_center', 'bad_job_fair', 'low_recognition', 'trap_major', 'forced_factory'],
    'admin': ['slow_admin', 'bad_counselor', 'formalism', 'unfair_scholarship', 'no_feedback_channel', 'random_plan_change', 'bureaucracy'],
    'mental': ['no_counseling', 'no_room_change', 'bad_club'],
}


# ============================================================
# 学校详细信息 & 评论池
# ============================================================
SCHOOL_REVIEWS_DATA = [
    # ==================== 安徽 (4所) ====================
    {
        'name': '安徽工业大学',
        'city': '马鞍山',
        'province': '安徽',
        'stype': '理工',
        'slevel': '普通',
        'comments': [
            {'major': '材料科学与工程', 'comment': '安工大在安徽理工类里算可以的，冶金和材料是传统强项，毕竟是原华东冶金学院出身。宿舍条件马鞍山校区还行，四人间上床下桌有空调，但部分老楼是六人间。食堂佳山校区和秀山校区水平参差，秀山食堂三楼不错。就业去宝武马钢、铜陵有色这些省内冶金企业的很多，稳定但天花板不高。'},
            {'major': '会计学', 'comment': '安工大的会计学在安徽普本里算小有名气，老师们挺负责。秀山校区是主校区，宿舍条件整体还行，四人间有空调独卫，水电平摊不贵。食堂秀山一楼便宜二楼好吃，推荐麻辣香锅和牛肉面。学校在马鞍山，离南京近，周末去南京玩很方便。就业主要往长三角制造业财务岗走。'},
            {'major': '计算机科学与技术', 'comment': '安工大计算机学院这几年在扩建，实验室设备更新了。秀山校区环境算马鞍山最好的，靠近雨山湖，绿化不错。宿舍四人间有空调，但晚上11点断电有点烦。食堂口味偏重，徽菜风味。整体来说安安稳稳读书可以，考研氛围浓。就业去合肥和南京居多。'},
            {'major': '机械工程', 'comment': '机械是安工大老牌专业，校企合作比较多，大三可以去马钢实习。宿舍条件看运气，新宿舍楼四人间有独卫空调，旧楼就比较一般了。食堂秀山万达食堂选择多，价格在安徽算中等。马鞍山生活成本低，一个月1500够花。省内就业认可度还行，省外就一般了。'},
        ]
    },
    {
        'name': '安徽理工大学',
        'city': '淮南',
        'province': '安徽',
        'stype': '理工',
        'slevel': '普通',
        'comments': [
            {'major': '土木工程', 'comment': '安理大由原淮南矿业学院升格，安全工程和土木是老牌强项，煤层气和地下工程很有特色。学校在淮南，山南新校区条件不错，四人间上床下桌有空调。老校区在市区但宿舍旧。新校区食堂很大三层楼，炸鸡饭和铁板饭不错。就业去煤炭系统和建筑企业的多，稳定但地点偏。'},
            {'major': '自动化', 'comment': '安理大自动化专业就业不错，学校有煤矿电气化背景，实验室设备够用。山南新校区2016年启用，各项设施都新，宿舍四人间独卫空调齐全。校园面积大，绿化好，就是淮南城市破旧了些。食堂价格便宜，一荤一素8块钱搞定。考研率比较高，学校学风还可以。'},
            {'major': '安全工程', 'comment': '安理大安全工程全国有名，毕竟原煤炭部直属高校，煤矿安全是传统强项。新校区宿舍条件确实良心，四人间独卫空调电梯楼。淮南有八公山和豆腐宴，生活安逸物价低，但城市发展一般。食堂百川和义苑都不错。就业去煤矿安全监察局和大型矿业集团的挺多，稳定但环境特殊。'},
            {'major': '计算机科学与技术', 'comment': '安理大计算机是新兴专业，师资中等偏上。新校区宿舍条件确实良心，四人间独卫空调电梯楼。食堂三家，百川和义苑不错。学校最大的优势是新校区设施好，最大劣势是淮南这座城市——没地铁、空气差、就业机会少。适合想考研跳出淮南的人。'},
        ]
    },
    {
        'name': '安徽工程大学',
        'city': '芜湖',
        'province': '安徽',
        'stype': '理工',
        'slevel': '普通',
        'comments': [
            {'major': '设计学', 'comment': '安工程的设计类专业在安徽普本里挺出名，艺术设计学院规模大。学校在芜湖，城市幸福感高，比合肥宜居。宿舍六人间为主没有独立卫浴，公共澡堂，这在南方有点痛苦。食堂二食堂的煲仔饭和麻辣烫不错。芜湖有方特和步行街，周末不无聊。就业去长三角设计公司和互联网公司的挺多。'},
            {'major': '车辆工程', 'comment': '安工程车辆工程对接芜湖奇瑞汽车，产学研合作紧密，实习机会多。宿舍条件老校区一般，新宿舍楼在建中。芜湖是奇瑞大本营，毕业生进奇瑞和配套企业的很多。食堂种类多安徽风味为主，价格便宜。学校整体普通水平，但在芜湖本地就业有优势。'},
            {'major': '计算机科学与技术', 'comment': '安工程计算机不算强但够用，老师水平中等。宿舍不太行，六人间没独卫是硬伤，洗澡要去大澡堂。校园在市中区交通方便。芜湖城市加分不少，比合肥节奏慢消费低。就业主要去合肥和江浙的中小企业，大厂很少来校招。适合安徽本地考生。'},
            {'major': '自动化', 'comment': '安工程自动化在安徽普本里算中游，实验设备够本科教学。宿舍条件是一大槽点，老校区六人间公共卫生间，新楼正在盖希望早日投入使用。好在芜湖城市不错，长江边风景好生活舒适。就业往芜湖本地制造业和合肥去的多。整体来说分数性价比还可以。'},
        ]
    },
    {
        'name': '安徽建筑大学',
        'city': '合肥',
        'province': '安徽',
        'stype': '理工',
        'slevel': '普通',
        'comments': [
            {'major': '建筑学', 'comment': '安建大建筑学在安徽是仅次于合工大的存在，五年制教学体系完整。南校区在经开区，宿舍四人间上床下桌有空调，北校区老一些。建筑学有自己的专教，通宵画图是常态。食堂南苑和北苑都还行，北苑二楼蛋包饭很火。就业去安徽建工集团和省内设计院的很多，在合肥认可度不错。'},
            {'major': '土木工程', 'comment': '安建大土木是招牌专业，省内建筑行业校友遍布。学校北校区在老城区南校区在经开区，土木主要在南北区都有。宿舍条件南校区好于北校区，均有空调。食堂南北各有千秋，南苑食堂可以。考研氛围不错，合工大和浙大是主要目标。就业在安徽建筑行业绝对够用。'},
            {'major': '环境工程', 'comment': '安建大环境工程依托建筑背景偏市政方向，给排水是特色。学校在合肥，这座城市发展快，地铁高铁都通了。宿舍南区四人间独卫空调很好，北区就一般了。食堂南区选择多价格适中。整体来说安建大在安徽普本里属于中上水平，校园环境和硬件逐年改善。'},
        ]
    },
    # ==================== 山西 (1所) ====================
    {
        'name': '太原科技大学',
        'city': '太原',
        'province': '山西',
        'stype': '理工',
        'slevel': '普通',
        'comments': [
            {'major': '机械工程', 'comment': '太科大的机械是王牌，重型机械和起重运输机械全国有名。学校在主校区（万柏林区），宿舍六人间为主没独卫，部分新楼四人间有空调。食堂一般，价格便宜一顿七八块。太原空气不太好冬天有雾霾。就业往太重、徐工、三一重工这些重工企业去的多，机械行业认可度不错。'},
            {'major': '自动化', 'comment': '太科大自动化专业偏重工业控制，跟山西煤机产业联系紧密。宿舍条件算山西高校平均水平——六人间公共卫生间，有暖气冬天不冷。食堂一二三餐都去过，都挺一般的。学校在太原市区交通方便。就业方向主要是山西本地重工和制造业，也有去北京天津的。整体在山西普本里算中上。'},
            {'major': '计算机科学与技术', 'comment': '太科大计算机近年有发展但不算强项，师资偏年轻。宿舍条件是比较大的短板，六人间上下铺公共卫浴。太原的生活成本很低，一个月一千出头够了。学校位于市区出行方便。就业上计算机毕业生去北京的不少，但校招大厂基本不来。适合山西本地考生想读工科的，分数不高性价比尚可。'},
            {'major': '材料科学与工程', 'comment': '太科大材料专业依托重型机械特色，在轧制和成型方面有优势。宿舍条件整体一般，老校区宿舍六人间无空调（太原夏天也不热）。食堂菜偏咸，面食做得好。太重和太原钢铁是主要就业去向。整体评价：在山西算可以，出去就不够看了，适合省内考生。'},
        ]
    },
    # ==================== 广东 (1所 专科) ====================
    {
        'name': '茂名职业技术学院',
        'city': '茂名',
        'province': '广东',
        'stype': '理工',
        'slevel': '普通',
        'comments': [
            {'major': '计算机科学与技术', 'comment': '茂职院是高职专科，计算机专业偏应用，教的都是实操技能。学校在茂名市区，宿舍6-8人间为主有空调，公共卫浴。食堂便宜一顿6-10块，茂名是海滨城市海鲜不贵。校园不大但该有的都有。就业主要去珠三角的IT中小企业做实施运维，专科起点工资不高但广东就业机会多。'},
            {'major': '机械工程', 'comment': '茂职院机械专业动手实训多，跟茂名石化产业有合作。宿舍条件就是专科标准，六到八人间有空调。学校管理严格，有晚自习和查寝。茂名生活节奏慢，消费低。毕业生进石化企业工厂和珠三角制造业的多。在广东专科里算中等偏上，比上不足比下有余。'},
            {'major': '电子商务', 'comment': '茂职院电商专业紧跟广东电商产业，有校企合作实训。宿舍条件一般，八人间为主。学校在茂名市区不算偏，周边生活便利。茂名作为四线城市消费很低，一个月800就够。就业方向主要是粤西和珠三角的电商运营客服岗位。如果想留广东又分数不够本科，可以拿茂职院当跳板。'},
        ]
    },
    # ==================== 江西 (3所) ====================
    {
        'name': '赣南医科大学',
        'city': '赣州',
        'province': '江西',
        'stype': '医药',
        'slevel': '普通',
        'comments': [
            {'major': '临床医学', 'comment': '赣医大在江西医学类排第三（仅次于南大医学院和江西中医药），临床医学五年制培养体系完整。学校黄金校区在赣州蓉江新区，宿舍四人间上床下桌有空调独卫。食堂二楼的粉蒸肉和瓦罐汤有江西特色。附属第一医院是赣州最好的三甲。就业主要在赣南和粤北的医院，考研去南方医和广州医的很多。'},
            {'major': '麻醉学', 'comment': '赣医大麻醉学是特色专业，在江西地级市医院里赣医毕业的麻醉医生很多。宿舍条件新校区不错，老校区就差一些。赣州是江西最大地级市，但经济一般城市不够繁华。食堂瓦罐汤和南昌拌粉不错。学校学风浓厚，医学生都挺卷的。就业在赣南粤北地区够了，想去南昌或广州得考研。'},
            {'major': '护理学', 'comment': '赣医大的护理学实操训练多，有仿真模拟病房。学校黄金校区环境好，宿舍四人间独卫空调。赣州生活节奏慢消费低。护理就业率很高，珠三角医院经常来赣医招人。整体来说赣医大对得起它的分数，在医学类专科院校里属于中游偏上水平。'},
            {'major': '药学', 'comment': '赣医大药学有制药工程方向，跟赣州青峰药业等有合作。新校区宿舍条件确实不错，四人间空调独卫。校园在赣州新区周边还在发展。食堂江西风味偏辣，三食堂小炒不错。就业去药企和医院的药房都行，考研率也比较高。在医学类普本里性价比不错。'},
        ]
    },
    {
        'name': '赣南师范大学',
        'city': '赣州',
        'province': '江西',
        'stype': '师范',
        'slevel': '普通',
        'comments': [
            {'major': '汉语言文学', 'comment': '赣南师大中文系历史悠久，古代文学和现当代文学师资不错。学校黄金校区宿舍四人间上床下桌有空调，比老校区好得多。校园环境不错，有明湖和樱花大道。食堂一楼的拌粉和三楼的麻辣香锅是经典。赣州空气质量好但经济一般。师范生就业主要去赣南和广东的中学，考研去华南师大和福建师大的多。'},
            {'major': '教育学', 'comment': '赣南师大教育学面向基础教育培养，在赣南地区中小学教育界校友众多。宿舍新校区条件好，四人间空调独卫。赣州生活成本低，适合静心读书。食堂品种不算多但价格实惠。学校有红色文化教育特色，毕竟赣州是苏区。就业在江西地级市做老师很稳，珠三角也能去。'},
            {'major': '英语', 'comment': '赣南师大英语师范是传统专业，有外教和语言实验室。宿舍条件新校区确实不错，但大一可能去老校区过渡。校园绿化好，适合散步跑步。赣州这座城市比较安逸，适合不太想卷的人。就业做中小学英语老师是主流，也有去培训机构和企业外贸的。整体在江西师范类里排第三（在江西师大和赣南师大后面？其实赣南师大就是江西第二师范院校）。'},
            {'major': '美术学', 'comment': '赣南师大美术学院在赣南地区有影响力，国画和油画方向有特色。宿舍看分到哪，新校区四人间旧校区六人间。校园环境好，章江边适合写生。食堂味道一般但管饱。赣州老城区有宋城墙和古浮桥，文化底蕴足。就业方向是中小学美术老师和培训机构。对分数不高的江西考生来说性价比挺高。'},
        ]
    },
    {
        'name': '宜春学院',
        'city': '宜春',
        'province': '江西',
        'stype': '综合',
        'slevel': '普通',
        'comments': [
            {'major': '汉语言文学', 'comment': '宜春学院是综合性地方院校，中文系师资还算可以。学校在宜春市区，宿舍四人间六人间都有，新宿舍有空调独卫。校园不大但绿化好，有一个沁湖。食堂便宜一餐8块管饱。宜春被称为"月亮之都"，温泉很有名，生活很安逸。就业在宜春本地和周边地市，考研氛围一般。适合江西本地考生。'},
            {'major': '计算机科学与技术', 'comment': '宜春学院计算机不算强，但基础教学够用。宿舍条件参差不齐，新宿舍楼不错旧的就一般。学校就在宜春市区，出门就是商业街。宜春这个城市很小但宜居，空气好温泉多。食堂二楼的麻辣香锅推荐。就业去南昌和深圳的小公司为主，大厂基本不来。分数不高又想读本科可以考虑。'},
            {'major': '护理学', 'comment': '宜春学院医学院有护理专业，依托宜春市人民医院。宿舍看校区，医学院校区可能旧一些。宜春生活节奏慢消费低，适合养老式学习。食堂一般但外面小吃街便宜。护理就业率还不错，医院护士缺口大，珠三角医院常来招人。整体评价：分数够本科线但不够好学校的选择。'},
            {'major': '法学', 'comment': '宜春学院法学在江西普本里不算出名，法考通过率中等。学校综合性强各种专业都有，学习氛围一般需要自律。宿舍有新有旧看运气。宜春这座城市环境好空气优，但就业机会少。法学生主要考公和考研，法考后再考虑就业。在江西各地级市基层法院检察院还能找到位置。'},
        ]
    },
    # ==================== 河北 (2所) ====================
    {
        'name': '石家庄铁道大学',
        'city': '石家庄',
        'province': '河北',
        'stype': '理工',
        'slevel': '普通',
        'comments': [
            {'major': '土木工程', 'comment': '铁大是原铁道兵工程学院转制，土木和交通工程全国有名，铁路系统里铁大毕业生遍布。学校本部在石家庄北二环，宿舍六人间为主无独卫，但新公寓在建条件在改善。食堂学一和综餐不错，价格便宜。石家庄空气质量一般。就业去中铁、中铁建、国铁集团的超级多，稳定但工作地点常年在野外项目上。'},
            {'major': '机械工程', 'comment': '铁大机械专业强在工程机械和铁道装备方向，与铁路系统对接紧密。宿舍老校区六人间公共卫浴，新校区条件好一些。石家庄作为省会城市水平一般，但交通枢纽去哪都方便。食堂的刀削面和炒饼不错。就业去铁路局和工程局的很多，工资稳定但不高的那种。铁大在行业内口碑很好。'},
            {'major': '计算机科学与技术', 'comment': '铁大计算机偏铁路信息化方向，有轨道交通特色。宿舍条件在石家庄高校里算中等，六人间为主。学校管理比较严，毕竟是军校改制背景。校园不大但五脏俱全。就业除了去IT公司外，去铁路系统的信息化岗位也是个稳定选择。整体来说铁大是一所性价比不错的工科院校。'},
            {'major': '电气工程及其自动化', 'comment': '铁大电气强在铁道电气化和牵引供电方向，跟铁路局合作密切。宿舍六人间没独卫是主要槽点，石家庄冬天有暖气还行。学校学风还可以考研率不低。就业主要去铁路局供电段和工程局电气化公司，也有去国家电网的但不如电力院校多。铁大分数不高但就业稳定，适合求稳的考生。'},
        ]
    },
    {
        'name': '河北工程大学',
        'city': '邯郸',
        'province': '河北',
        'stype': '理工',
        'slevel': '普通',
        'comments': [
            {'major': '土木工程', 'comment': '河工程由原河北建筑科技学院、邯郸医专等合并而成，土木建筑是传统强项。主校区在邯郸，宿舍六人间上床下桌有空调，部分新楼有四人间。校园挺大绿化不错，有一个大的人工湖。邯郸是古都但城市发展一般，空气污染在河北算中等。食堂三餐都有，价格便宜。就业去河北建工和京津建筑企业。'},
            {'major': '机械工程', 'comment': '河工程机械专业偏建筑机械和矿山机械方向，有工程实践传统。宿舍条件在医学院校区一般，六人间为主。邯郸这座城市历史底蕴深但经济一般，适合安静读书。食堂主校区二餐厅不错。就业在邯郸及河北各地制造业。整体在河北省内属于普通水平，分数不高值得考虑。'},
            {'major': '水利水电工程', 'comment': '河工程水利专业依托邯郸周边水资源工程，有岳城水库等实践基地。主校区宿舍有空调，河北夏天也挺热的。校园大环境好，邯郸生活成本低。食堂推荐主校区二餐厅。就业去河北水利系统和京津企业的多，工作稳定。学校整体就是河北省内普通一本水平，没有太多亮点但也对得起分数。'},
            {'major': '计算机科学与技术', 'comment': '河工程计算机不算学校强项，但本科教学没问题。宿舍条件在河北高校里算中等偏上，多数装了空调。邯郸这个城市优点是生活成本极低，缺点是没啥就业机会。考研氛围比较浓，目标多是京津高校。整体评价：适合不想离家太远的河北考生，毕业多半去北京天津。'},
        ]
    },
    # ==================== 河南 (6所) ====================
    {
        'name': '河南师范大学',
        'city': '新乡',
        'province': '河南',
        'stype': '师范',
        'slevel': '普通',
        'comments': [
            {'major': '教育学', 'comment': '河师大在河南师范类排第二（仅次于河大），教育学有深厚底蕴。学校在新乡市区，宿舍六人间为主有空调（近年陆续装了）。东校区新宿舍条件好于西区。校园绿树成荫，有一个大的中心花园。食堂万人餐厅的茄汁面和学苑餐厅的麻辣烫不错。就业在河南各地市中小学教师招聘中很有竞争力。'},
            {'major': '汉语言文学', 'comment': '河师大中文系在河南享有盛誉，教授治学严谨。西校区宿舍条件一般，六人间上下铺，但空调全覆盖了。新乡城市不大但物价低，生活惬意。食堂品种丰富河南面食做得好。师范生享受公费师范政策的话工作包分配。非师范的考研率高，去河大郑大和华师的多。整体来说河师大的学风很好。'},
            {'major': '数学与应用数学', 'comment': '河师大数学与应用数学是王牌专业之一，考研率在师范院校里名列前茅。宿舍东区好于西区，新宿舍四人间有空调独卫。新乡离郑州近高铁20分钟，周末去郑州玩很方便。食堂西区万人餐厅便宜大碗。就业做中学数学老师是主流，河南的中学对河师大毕业生认可度很高。'},
            {'major': '计算机科学与技术', 'comment': '河师大计算机非师范方向近年来有发展，实验室条件在改善。宿舍条件整体在改善中，西区老宿舍比较艰苦。新乡生活成本低，食堂的饸饹面和胡辣汤是特色。计算机专业就业去郑州的比较多。河师大整体是一所低调务实的师范院校，适合想当老师的河南考生。'},
        ]
    },
    {
        'name': '河南理工大学',
        'city': '焦作',
        'province': '河南',
        'stype': '理工',
        'slevel': '普通',
        'comments': [
            {'major': '安全工程', 'comment': '河理工安全工程全国前三，矿业安全特色极其鲜明，原焦作矿院出身。学校南校区（新校区）条件好，四人间上床下桌空调独卫，北校区老一些。焦作是矿业城市但近年转型旅游——云台山就在旁边。食堂南校区学府餐厅的烩面和学士餐厅的麻辣香锅很赞。就业去煤矿安全监察局和大型矿业集团的很多。'},
            {'major': '测绘工程', 'comment': '河理工测绘工程全国有名，有测绘科学与技术博士点。南校区硬件确实不错，宿舍四人间空调独卫。校园大占地4000亩，在河南高校里算大的。焦作城市小但生活安逸物价低。食堂品种多价格便宜。就业去国家测绘系统和地理信息企业的多。河理工在工科领域比很多211都强，分数性价比极高。'},
            {'major': '机械工程', 'comment': '河理工机械偏矿用机械方向，教学扎实就业稳定。南校区宿舍条件在河南高校里属于上等水平。校园环境好，学校内有山有湖。焦作有云台山，周末爬山好去处。食堂学苑的牛肉面经典。就业去矿山机械企业和制造业的都有。整体评价：河理工是河南工科最强普本，学科实力比不少211都强。'},
            {'major': '计算机科学与技术', 'comment': '河理工计算机是新兴热门专业，依托学校的工科氛围发展不错。南校区宿舍条件好，四人间空调独卫。校园大到需要骑自行车上课。焦作离郑州一小时车程。就业去郑州IT企业的多，考研去郑大和华科的也不少。河理工是河南"双非"里实力最强的学校之一，值得考虑。'},
        ]
    },
    {
        'name': '河南工业大学',
        'city': '郑州',
        'province': '河南',
        'stype': '理工',
        'slevel': '普通',
        'comments': [
            {'major': '食品科学与工程', 'comment': '河工大粮油食品全国顶尖，原郑州粮食学院，是亚洲唯一的粮油食品专业院校。莲花街校区在郑州高新区，宿舍六人间上床下桌有空调，部分四人间。学校校园很大，图书馆不错。食堂一餐的油泼面和二餐的自选菜推荐。就业去中粮、益海嘉里、各大粮油集团的超多，食品行业校友网遍布全国。'},
            {'major': '机械工程', 'comment': '河工大机械偏粮机储运装备方向，跟中储粮系统合作紧密。莲花街校区宿舍六人间有空调，郑州夏天热空调必须的。郑州作为国家中心城市发展快，地铁通了去哪都方便。食堂三餐选择多价格适中。就业去粮机企业和制造业的多。河工大在河南普本里属于中上水平，粮油特色独树一帜。'},
            {'major': '土木工程', 'comment': '河工大土木工程在粮仓建筑和筒仓结构方面有独特优势。宿舍莲花街校区六人间空调，嵩山路校区老一些。校园在郑州高新去，周边有公园和商业配套。郑州这座城市就业机会多，房价在省会里算低的。食堂三餐的油泼面很火。整体来说河工大特色鲜明，在粮油食品领域就是全国NO.1。'},
            {'major': '计算机科学与技术', 'comment': '河工大计算机学院近年扩招，师资以年轻博士为主。宿舍莲花街校区有空调，郑州的夏天没有空调不行。校园大环境好，适合学习和生活。郑州IT就业市场在扩张，但大厂郑州office不多。河工大的优势是特色鲜明、在郑州地理位置好、分数亲民。'},
        ]
    },
    {
        'name': '华北水利水电大学',
        'city': '郑州',
        'province': '河南',
        'stype': '理工',
        'slevel': '普通',
        'comments': [
            {'major': '水利水电工程', 'comment': '华水水利全国知名，水利部与河南省共建，水利工程学科评估B+。龙子湖校区在郑州东区，宿舍六人间有空调（新楼四人间）。校园环境好龙子湖畔景色宜人。食堂一餐和二餐都不错，推荐一餐的羊肉烩面。就业去水利部下属单位和各省水利设计院的特别多，南水北调、黄河水利委员会都是主要去向。'},
            {'major': '土木工程', 'comment': '华水土木偏水工结构方向，跟水利建筑紧密结合。龙子湖校区宿舍有空调，郑州夏天必备。校园东临龙子湖西靠地铁，交通便利。食堂三餐的砂锅面不错。就业去水利水电工程局和建筑企业的多。华水在水利行业的地位就像河工大在粮油行业的地位一样，行业内认可度极高。'},
            {'major': '地质工程', 'comment': '华水地质工程强在工程地质与水文地质，跟水利工程密切配合。宿舍六人间有空调，新宿舍楼在陆续建。校园在郑州东区大学城，周边大学多交流方便。食堂二楼的盖浇饭不错。就业去水电勘察设计院和地质工程公司的多。华水整体是一所以工科为主、水利为特色的高校，河南考生中分段的好选择。'},
            {'major': '计算机科学与技术', 'comment': '华水计算机虽然不如水利强势，但水利信息化方向有特色。龙子湖校区宿舍条件在郑州高校里中等。校园环境好适合学习。郑州IT就业市场在增长。整体来说华水分数不算高但在水利行业地位高，适合对水利感兴趣或者想要稳定就业的考生。'},
        ]
    },
    {
        'name': '郑州轻工业大学',
        'city': '郑州',
        'province': '河南',
        'stype': '理工',
        'slevel': '普通',
        'comments': [
            {'major': '设计学', 'comment': '郑轻工的设计类专业在河南很有名，尤其是工业设计和视觉传达。东风校区在市区，宿舍六人间为主有空调。科学校区在高新区条件好一些。食堂东风校区的一餐便宜，科学校区清餐的拉面不错。郑州城市发展快，设计类就业机会多。在轻工业产品设计和食品包装设计领域，郑轻工在河南就是老大哥。'},
            {'major': '食品科学与工程', 'comment': '郑轻工食品偏烟草和香精香料方向，原隶属轻工业部。科学校区宿舍四人间六人间都有空调。校园在郑州高新去环境不错。郑州生活成本适中。食堂学苑餐厅的椒麻鸡不错。就业去烟草系统、食品企业和香精公司的多。整体来说郑轻工是一所特色鲜明、就业不错的工科院校，在轻工领域有传承。'},
            {'major': '电气工程及其自动化', 'comment': '郑轻工电气工程在河南普本里算不错，强弱电都有涉及。科学校区宿舍有空调。郑州交通便利地铁通达。食堂推荐科学校区三餐。就业去电网和电气设备企业的都有。学校在轻工自动化生产线控制方面有积累。整体就是一所普通的河南省属工科院校，分数不高性价比还行。'},
        ]
    },
    # ==================== 福建 (3所) ====================
    {
        'name': '福建理工大学',
        'city': '福州',
        'province': '福建',
        'stype': '理工',
        'slevel': '普通',
        'comments': [
            {'major': '土木工程', 'comment': '福理工（原福建工程学院）土木建筑是王牌，百年工科传承。旗山北校区宿舍四人间上床下桌空调独卫，鳝溪校区旧一些。学校在福州大学城，周边配套成熟。福州这个城市绿化好有福道和西湖，但夏天热。食堂旗山北区一楼便宜二楼好吃。就业去福建省内建筑设计和施工企业的多，在福建建筑行业校友众多。'},
            {'major': '建筑学', 'comment': '福理工建筑学五年制，在福建省内仅次于厦大和福大。旗山校区新宿舍条件好，四人间空调独卫。校园内有建筑系馆和专业教室，通宵画图文化浓厚。福州夏天闷热但宿舍有空调不怕。食堂北区三餐的沙县小吃和捞化是特色。就业去福建省建筑设计院和地产公司的多。分数不高想学建筑可以考虑。'},
            {'major': '计算机科学与技术', 'comment': '福理工计算机是新兴重点发展学科，实训楼设备新。旗山校区宿舍条件在福州高校里算不错的。福州有马尾自贸区和软件园，IT就业机会不少。食堂三餐的鱼丸和肉燕不错，福州特色。福理工近年来改名后分数线在涨，综合实力在福建普本里处于中上位置。'},
            {'major': '机械工程', 'comment': '福理工机械偏装备制造方向，跟福建制造业对接。旗山校区宿舍条件好。福州城市生活舒适，有山有海。食堂推荐早餐的锅边糊和午餐的荔枝肉。就业去宁德时代、东南汽车、福耀玻璃等福建名企的多。福理工在福建工科院校里排第三（在福大和华侨之后），性价比不错。'},
        ]
    },
    {
        'name': '闽南师范大学',
        'city': '漳州',
        'province': '福建',
        'stype': '师范',
        'slevel': '普通',
        'comments': [
            {'major': '教育学', 'comment': '闽南师大是福建两所省属师范之一，教育学有闽南文化研究特色。圆山校区新宿舍条件好，四人间空调独卫。江滨校区偏文科在市区。漳州这个城市很适合生活，慢节奏美食多。食堂江滨校区的沙茶面和圆山校区的卤面是招牌。就业在闽南地区（厦漳泉）中小学当老师认可度很高，尤其漳州本地。'},
            {'major': '汉语言文学', 'comment': '闽南师大中文系有闽南文化和方言研究特色，师资在福建省内不错。圆山校区新宿舍条件好，建议选新校区。漳州离厦门近高铁20分钟，周末去厦门玩很方便。漳州小吃多面煎粿、四果汤、麻糍都好吃。就业方向以中小学语文教师为主，也有很多考公务员的。整体在福建省属高校里处于中等水平。'},
            {'major': '应用化学', 'comment': '闽南师大化学偏应用方向，跟漳州石化产业有合作。宿舍圆山校区好江滨校区旧。漳州是著名的水仙花之乡和水果之乡，环境好生活安逸。食堂的闽南风味菜做得地道。就业去厦门和漳州的化工企业和药企的比较多。闽南师大在福建师范类排第二（福建师大之后），是闽南地区教师培养的重要基地。'},
            {'major': '历史学', 'comment': '闽南师大历史学有闽台区域研究特色，跟闽南文化一脉相承。圆山校区新宿舍条件好。漳州古城有历史底蕴，适合历史学学生。生活成本比厦门低一半以上。就业主要做历史老师或者文博单位。整体来说闽南师大是一所低调务实的地方师范院校，适合想留闽南发展的考生。'},
        ]
    },
    {
        'name': '泉州师范学院',
        'city': '泉州',
        'province': '福建',
        'stype': '师范',
        'slevel': '普通',
        'comments': [
            {'major': '小学教育', 'comment': '泉州师院小学教育是传统强项，培养泉州地区小学教师的主要基地。主校区在东海，宿舍六人间为主有空调，部分新楼四人间。泉州是海上丝绸之路起点，文化底蕴深，城市经济好民营经济发达。食堂二餐的闽南卤面和三餐的面线糊推荐。就业在泉州地区当小学老师非常稳，泉州教育系统校友遍布。'},
            {'major': '汉语言文学', 'comment': '泉州师院中文系师资在福建地方师范里算不错的，有闽南文化研究方向。东海校区靠海，宿舍六人间有空调。泉州这座城市太棒了，古城区有开元寺西街，现代有万达，美食天堂。食堂推荐面线糊和润饼。就业方向以中小学语文教师和公务员为主。泉州师院在泉州本地认可度很高。'},
            {'major': '音乐表演', 'comment': '泉州师院音乐与舞蹈学院有南音方向特色，传承闽南传统音乐。东海校区环境好靠海边。泉州作为东亚文化之都，音乐文化氛围浓厚。食堂闽南特色小吃不错。就业在泉州做音乐老师或者文化传承工作都行。整体来说泉州师院是一所扎根泉州的地方师范院校，对得起分数在泉州就业没问题。'},
            {'major': '英语', 'comment': '泉州师院英语师范在泉州认可度高，泉州外向型经济发达对英语需求大。东海校区靠海环境好，宿舍有空调。泉州生活成本适中，小吃丰富面线糊土笋冻四果汤都值得一试。就业方向做中小学英语老师或者外贸企业的多。泉州师院整体在福建省属高校里属于中游水平，适合想留闽南的考生。'},
        ]
    },
]


def get_major_id(cursor, major_name, allowed_cats):
    """Get a major ID by name, checking it belongs to allowed categories."""
    cursor.execute("SELECT id, category FROM majors WHERE name = ?", (major_name,))
    row = cursor.fetchone()
    if row and row[1] in allowed_cats:
        return row[0]
    # Fallback: any major in allowed categories
    for cat in allowed_cats:
        cursor.execute("SELECT id FROM majors WHERE category = ? ORDER BY id LIMIT 1", (cat,))
        row = cursor.fetchone()
        if row:
            return row[0]
    return 9  # last resort: 法学


def generate_answers_from_comment(comment, school_info, scores):
    """Generate plausible answers dict from comment content and scores."""
    answers = {}
    # Default: random answers weighted by category scores
    for cat_key, qs in QUESTIONS_BY_CAT.items():
        cat_score = scores.get(cat_key, 3.0)
        for q in qs:
            if random.random() < (cat_score - 1) / 4:
                answers[q] = random.choice([True, True, False])
            else:
                answers[q] = random.choice([True, False, False])

    # Override based on comment clues - positive clues
    pos_clues = ['条件好', '条件不错', '有空调', '独卫', '上床下桌', '四人间', '新宿舍', '新校区']
    neg_clues = ['条件一般', '条件差', '六人间', '没独卫', '公共', '旧', '上下铺']

    # Academic
    if any(w in comment for w in ['卷', '学霸', '学风浓厚', '考研氛围']):
        answers['forced_run'] = False
        answers['forced_study'] = False
    if '选课' in comment:
        answers['hard_course_select'] = True

    # Dormitory
    if '有空调' in comment or '空调' in comment:
        answers['has_ac'] = True
    if '独卫' in comment or '独立卫浴' in comment:
        answers['private_bathroom'] = True
    if '四人间' in comment or '上床下桌' in comment:
        answers['over_6_room'] = False
        answers['bunk_bed'] = False
    if '六人间' in comment or '上下铺' in comment:
        answers['over_6_room'] = True
        answers['bunk_bed'] = True
    if '断电' in comment:
        answers['power_limit'] = True
    if '公共' in comment or '公共卫浴' in comment or '大澡堂' in comment:
        answers['private_bathroom'] = False

    # Employment
    if '就业' in comment:
        if any(w in comment for w in ['认可度高', '很好', '不错', '无忧', '稳定', '抢着要', '不愁']):
            answers['low_recognition'] = False
            answers['fake_employment_rate'] = random.choice([True, False])
        elif any(w in comment for w in ['困难', '不行', '一般', '不够看']):
            answers['low_recognition'] = True
            answers['fake_employment_rate'] = True

    return answers


def main():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Load all schools
    all_schools = {}
    c.execute("SELECT id, name, province, type, level FROM schools")
    for sid, sname, sprv, stype, slevel in c.fetchall():
        all_schools[sname] = {'id': sid, 'province': sprv, 'type': stype, 'level': slevel}

    # Load majors by category
    c.execute("SELECT id, name, category FROM majors")
    majors_by_cat = {}
    for mid, mname, mcat in c.fetchall():
        majors_by_cat.setdefault(mcat, []).append((mid, mname))

    total_inserted = 0
    next_device_seq = 10000

    for school_data in SCHOOL_REVIEWS_DATA:
        name = school_data['name']
        if name not in all_schools:
            print(f"  WARNING: {name} not found in DB, skipping")
            continue

        school = all_schools[name]
        sid = school['id']
        stype = school['type']
        sprv = school['province']
        slevel = school['level']
        allowed_cats = MAJOR_MATCH.get(stype, ['文学'])
        province_adj = PROVINCE_ADJ.get(sprv, {})
        level_bonus = LEVEL_BONUS.get(slevel, 0.0)

        print(f"\nProcessing: {name} (id={sid}, {sprv}, {stype}, {slevel})")

        reviews = school_data.get('comments', [])
        for ri, rdata in enumerate(reviews):
            major_name = rdata['major']
            comment = rdata['comment']

            # Get major ID
            mid = get_major_id(c, major_name, allowed_cats)

            # Generate scores
            scores = {}
            for cat in CAT_KEYS:
                base = 3.0 + random.uniform(-0.3, 0.3)
                if cat in province_adj:
                    base += province_adj[cat]
                scores[cat] = round(max(1.0, min(5.0, base)), 1)

            # Add level bonus
            if level_bonus > 0:
                scores['academic'] = min(5.0, round(scores['academic'] + level_bonus * 0.5, 1))
                scores['employment'] = min(5.0, round(scores['employment'] + level_bonus * 0.5, 1))

            overall = round(sum(scores.get(k, 3.0) * CAT_WEIGHTS.get(k, 10) for k in CAT_KEYS) / sum(CAT_WEIGHTS.values()), 1)

            # Generate tags
            tags = []
            d = scores.get('dormitory', 3.0)
            c_val = scores.get('cafeteria', 3.0)
            e_val = scores.get('employment', 3.0)
            env = scores.get('environment', 3.0)

            if d >= 4.0: tags.append("宿舍豪华")
            elif d <= 2.2: tags.append("宿舍破旧")
            if c_val >= 4.0: tags.append("食堂神仙")
            elif c_val <= 2.2: tags.append("食堂地狱")
            if e_val >= 4.0: tags.append("就业无忧")
            elif e_val <= 2.5: tags.append("就业困难")
            if env >= 4.0: tags.append("校园巨美")
            elif env <= 2.5: tags.append("校园荒凉")
            if random.random() < 0.3: tags.append("内卷严重")
            if random.random() < 0.3: tags.append("老师超好")
            if random.random() < 0.2: tags.append("社团丰富")
            if random.random() < 0.15: tags.append("形式主义")
            if random.random() < 0.15: tags.append("空调自由")
            if d <= 2.5 and random.random() < 0.3: tags.append("空调绝缘")
            if random.random() < 0.1: tags.append("WiFi龟速")
            if random.random() < 0.1: tags.append("图书馆霸位")
            if any(w in comment for w in ['断电', '十一点断电']): tags.append("爬楼达人")
            # Pick 3-4 unique tags
            tags = list(set(tags))[:4]

            # Generate answers
            answers = generate_answers_from_comment(comment, school_data, scores)

            # Device ID
            device_id = hashlib.md5(f"ai-generator-missing-{name}-{ri}".encode()).hexdigest()[:16]

            # Insert
            answers_json = json.dumps(answers, ensure_ascii=False)
            cat_scores_json = json.dumps(scores, ensure_ascii=False)
            tags_json = json.dumps(tags, ensure_ascii=False)

            c.execute("""
                INSERT INTO reviews (school_id, major_id, device_id, answers, category_scores, overall_score, comment, tags, likes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (sid, mid, device_id, answers_json, cat_scores_json, overall, comment, tags_json, random.randint(0, 25)))

            total_inserted += 1
            print(f"  [{ri+1}] {major_name}: score={overall}, tags={tags}")

    conn.commit()
    conn.close()
    print(f"\n{'='*60}")
    print(f"Total: {total_inserted} reviews inserted across {len(SCHOOL_REVIEWS_DATA)} schools.")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
