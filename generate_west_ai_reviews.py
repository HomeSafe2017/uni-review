#!/usr/bin/env python3
"""
为云南、广西、海南、内蒙古、新疆、宁夏、青海、西藏、贵州、甘肃高校生成AI评价
"""
import sqlite3
import json
import random
import sys

random.seed(42)

DB_PATH = '/home/homesafe/projects/uni-review/data/uni_review.db'

# ============================================================
# 专业匹配规则
# ============================================================
# 综合→所有 / 理工→经济/法学(知产)/文学(外语)/理学/工学/管理
# 师范→哲学/经济/法学/教育/文学/历史/理学/管理/艺术
# 医药→仅医学 / 农林→经济/法学/文学/理学/工学/农学/管理
# 财经→经济/法学/文学/管理 / 政法→法学/文学
# 语言→文学/管理 / 艺术→文学/艺术
# 体育→教育(体育教育) / 民族→同综合

MAJOR_MATCH = {
    '综合': ['经济学','法学','文学','理学','工学','农学','医学','管理学','教育学','历史学','哲学','艺术学'],
    '理工': ['经济学','法学','文学','理学','工学','管理学'],
    '师范': ['哲学','经济学','法学','教育学','文学','历史学','理学','管理学','艺术学'],
    '医药': ['医学'],
    '农林': ['经济学','法学','文学','理学','工学','农学','管理学'],
    '财经': ['经济学','法学','文学','管理学'],
    '政法': ['法学','文学'],
    '语言': ['文学','管理学'],
    '艺术': ['文学','艺术学'],
    '体育': ['教育学'],
    '民族': ['经济学','法学','文学','理学','工学','农学','医学','管理学','教育学','历史学','哲学','艺术学'],
}

# ============================================================
# 评分调整
# ============================================================
ADJUSTMENTS = {
    '云南': {'dormitory': 0.0, 'cafeteria': 0.2, 'employment': -0.1, 'environment': 0.3},
    '广西': {'dormitory': 0.0, 'cafeteria': 0.1, 'employment': -0.1},
    '海南': {'dormitory': 0.1, 'cafeteria': 0.1, 'employment': 0.0, 'environment': 0.2},
    '内蒙古': {'dormitory': -0.2, 'cafeteria': -0.1, 'employment': -0.2},
    '新疆': {'dormitory': -0.2, 'cafeteria': -0.1, 'employment': -0.2},
    '宁夏': {'dormitory': -0.2, 'cafeteria': -0.1, 'employment': -0.2},
    '青海': {'dormitory': -0.2, 'cafeteria': -0.1, 'employment': -0.2},
    '西藏': {'dormitory': -0.2, 'cafeteria': -0.1, 'employment': -0.2},
    '甘肃': {'dormitory': -0.2, 'cafeteria': -0.1, 'employment': -0.2},
    '贵州': {'dormitory': 0.0, 'cafeteria': 0.1, 'employment': -0.1},
}

LEVEL_ADJ = {'985/211': 0.3, '211': 0.2, '双一流': 0.1, '普通': 0.0}

# ============================================================
# 名校库：学校ID -> 可用的major_id列表（按类别匹配后）
# ============================================================

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# 获取所有专业
cur.execute('SELECT id, name, category FROM majors')
all_majors = {m[0]: {'name': m[1], 'cat': m[2]} for m in cur.fetchall()}

# 按类别分组
majors_by_cat = {}
for mid, minfo in all_majors.items():
    cat = minfo['cat']
    if cat not in majors_by_cat:
        majors_by_cat[cat] = []
    majors_by_cat[cat].append(mid)

# 获取所有目标学校的详细信息
provinces = ['云南', '广西', '海南', '内蒙古', '新疆', '宁夏', '青海', '西藏', '贵州', '甘肃']
target_schools = []
for p in provinces:
    cur.execute('SELECT id, name, province, type, level FROM schools WHERE province = ? ORDER BY name', (p,))
    for row in cur.fetchall():
        target_schools.append({'id': row[0], 'name': row[1], 'province': row[2], 'type': row[3], 'level': row[4]})

print(f"Target schools: {len(target_schools)}")
for s in target_schools:
    print(f"  {s['id']}: {s['name']} ({s['province']}, {s['type']}, {s['level']})")

# ============================================================
# 获取下一个可用的device_id序号
# ============================================================
cur.execute("SELECT device_id FROM reviews WHERE device_id LIKE 'ai-generator-west-%'")
existing = set(r[0] for r in cur.fetchall())

# 计算已有device_id的最大序号
next_seq = 0
cur.execute("SELECT device_id FROM reviews WHERE device_id LIKE 'ai-generator-%'")
for r in cur.fetchall():
    parts = r[0].split('-')
    if len(parts) >= 3:
        try:
            n = int(parts[2])
            if n >= next_seq:
                next_seq = n + 1
        except:
            pass

# 再单独检查已有的west设备
for dev in existing:
    parts = dev.split('-')
    if len(parts) == 4 and parts[3].isdigit():
        n = int(parts[3])
        if n >= next_seq:
            next_seq = n + 1

print(f"\nStarting device_id sequence from: {next_seq}")

# ============================================================
# 为每个学校选择2-3个合适的专业
# ============================================================
def get_matching_majors(school_type):
    """根据学校类型获取匹配的专业类别"""
    cats = MAJOR_MATCH.get(school_type, MAJOR_MATCH['综合'])
    matched_ids = []
    for cat in cats:
        matched_ids.extend(majors_by_cat.get(cat, []))
    return matched_ids

def select_majors_for_school(school, count=3):
    """为学校选择count个专业"""
    matched_ids = get_matching_majors(school['type'])
    if not matched_ids:
        # 兜底
        matched_ids = list(all_majors.keys())
    # 随机选count个，尽量选不同类别的
    random.shuffle(matched_ids)
    selected = matched_ids[:count]
    return [(mid, all_majors[mid]['name'], all_majors[mid]['cat']) for mid in selected]

# ============================================================
# 评论模板（每个省份/学校类型定制化）
# ============================================================

def gen_comment(school, major_name, major_cat):
    """根据学校、专业生成个性化评论"""
    province = school['province']
    adj = ADJUSTMENTS.get(province, {})
    name = school['name']
    
    # 云南
    if province == '云南':
        if '大学' in name and '211' in school['level']:
            opts = [
                f"在{name}读{major_name}，学术氛围在西南地区算很不错的。呈贡校区硬件新，宿舍有四人间独卫阳台。食堂选择多，就是有些偏僻，去市区要一小时。春城气候加分，校园绿化好。就业的话省内认可度高，但想去一线城市竞争力一般。",
                f"{name}的{major_name}专业师资力量不错，东陆校区历史感满满，古树参天。呈贡校区条件更好但偏。食堂过桥米线和烧饵块令人怀念。整体环境宜人，适合静心读书。",
            ]
        elif '昆明理工' in name:
            opts = [
                f"昆明理工的{major_name}在云南工科里面算是头牌了。冶工特色鲜明，实验室设备更新不错。宿舍条件中等，六人间上下铺为主。食堂便宜管饱，莲华校区环境有历史感。就业在云南的工业口子很有竞争力。",
                f"昆工{major_name}专业就业面广，云南本地的制造业、建筑行业校友多。就是宿舍条件参差，新宿舍还行，老宿舍比较艰苦。好在昆明气候好，一年四季不用空调。",
            ]
        elif '云南师范' in name:
            opts = [
                f"云师的{major_name}在西南地区师范院校中排得上号。一二一校区在市中心，交通便利。食堂种类多味道好，价格亲民。宿舍条件一般，但校园环境优美，图书馆学习氛围浓。",
            ]
        elif '云南民族' in name:
            opts = [
                f"云南民族大学的{major_name}很有特色，雨花校区很大。少数民族文化氛围浓厚，各种民族节日活动多。宿舍四人间有独卫。食堂有民族特色窗口，味道不错。就业在云南本地有优势。",
            ]
        elif '昆明医科' in name:
            opts = [
                f"昆明医科大学的{major_name}在省内医疗系统认可度高。教学医院资源丰富，临床实践机会多。宿舍条件普通六人间。食堂中规中矩。好在昆明气候好不冷不热，适合学医。",
            ]
        elif '云南农业' in name:
            opts = [
                f"云南农大的{major_name}依托云南生物资源优势，特色明显。校园在盘龙江边，环境清幽。宿舍条件一般。食堂菜价便宜。就业方向多为农业系统。",
            ]
        elif '大理' in name:
            opts = [
                f"大理大学的{major_name}背靠苍山面朝洱海，风景绝了。气候四季如春，在这里读书心情都好很多。宿舍条件普通。学校不算强但环境实在是加分项。",
            ]
        else:
            opts = [f"在{name}读{major_name}，整体体验中规中矩。昆明气候确实好，校园环境不错。宿舍和食堂属于正常水平。就业方面在省内有一定认可度。"]
    
    # 广西
    elif province == '广西':
        if '广西大学' in name:
            opts = [
                f"西大的{major_name}在广西就是老大哥。校园超大，君武路两旁的大树很有感觉。宿舍条件参差不齐，东校园新宿舍好一些。食堂种类丰富，狗洞小吃街是回忆。就业在广西内很吃得开。",
                f"在{name}读{major_name}性价比不错，211牌子在本地够用。校园面积大，有个很大的湖。就是南宁夏天热，宿舍没空调的话比较煎熬。",
            ]
        elif '广西师范' in name:
            opts = [
                f"广西师大在桂林，环境没得说，王城校区就在景区里。育才校区在市中心。学{major_name}的话文科氛围好。宿舍老校区条件一般。物价不高，生活舒适。",
            ]
        elif '广西医科' in name:
            opts = [
                f"广西医科大的{major_name}在区内医学界地位很高。教学严格，实习医院多。宿舍六人间为主。食堂菜价便宜南宁口味偏清淡。就业基本覆盖广西各大医院。",
            ]
        elif '广西民族' in name:
            opts = [
                f"广西民族大学的{major_name}小语种是特色，东南亚语言优势明显。相思湖校区环境优美。宿舍条件一般有独卫。食堂东南亚风味窗口是亮点。",
            ]
        elif '桂林理工' in name:
            opts = [
                f"桂林理工的{major_name}在广西工科里算不错的。地质材料是传统优势。桂林山水甲天下，环境确实好。宿舍四人间有空调。就业在广西建筑地勘系统有口碑。",
            ]
        elif '桂林电子' in name:
            opts = [
                f"桂电的{major_name}在电子信息领域口碑不错。花江校区在山里环境好但偏。宿舍条件尚可。食堂一般。就业在珠三角有一定竞争力。",
            ]
        else:
            opts = [f"在{name}读{major_name}，整体体验还可以。广西物价不高生活压力小。就是就业机会相对少一些，很多人毕业后去珠三角发展。"]
    
    # 海南
    elif province == '海南':
        if '海南大学' in name:
            opts = [
                f"海大的{major_name}有热带特色。海甸校区在海口市中心，生活方便。宿舍四人间有空调和独卫，海口气候湿热没空调不行。食堂品种多但味道一般。热带农业和旅游管理是特色方向。就业留在海南的不少。",
                f"{name}的{major_name}依托海南自贸港发展前景不错。校园椰子树成片很有热带风情。宿舍条件在211中算中等偏上。就是海口夏天湿热，不过学校有空调还算能忍。",
            ]
        elif '海南师范' in name:
            opts = [
                f"海南师大的{major_name}在海南教育系统很有地位。桂林洋校区比较新，宿舍条件不错有空调独卫。海口生活节奏慢，适合学习。就是海口夏天确实热。",
            ]
        elif '海南医学' in name:
            opts = [
                f"海南医学院的{major_name}是海南唯一医学本科院校。附属医院资源在岛上最好。宿舍条件有空调。海口气候湿热但习惯了也还好。毕业后留海南发展是主流。",
            ]
        else:
            opts = [f"在{name}读{major_name}，海南的气候是最大特点。校园环境热带风情浓郁。宿舍基本有空调。生活节奏慢，适合安心学习。"]
    
    # 内蒙古
    elif province == '内蒙古':
        if '内蒙古大学' in name:
            opts = [
                f"内大的{major_name}在内蒙古是最高学府。211牌子在内蒙够用。北校区在市区生活方便。宿舍条件一般六人间。冬天暖气足但外面冷。食堂肉食多分量足。就业在区内有优势。",
                f"{name}的{major_name}师资在区内最好。校园不算大但环境整洁。最大的问题是地理位置偏远，去北京坐火车要很久。宿舍条件普通。",
            ]
        elif '内蒙古农业' in name:
            opts = [
                f"内蒙古农大的{major_name}以草原畜牧业为特色。校园大，实验牧场占地广。宿舍条件一般。食堂牛羊肉多而且便宜。冬天漫长寒冷。就业方向多为农牧系统。",
            ]
        elif '内蒙古工业' in name:
            opts = [
                f"内蒙古工业大学的{major_name}在区内工科有口碑。机械电力类专业强。宿舍六人间无独卫。食堂量足管饱。呼和浩特冬天冷，好在室内有暖气。",
            ]
        elif '内蒙古师范' in name:
            opts = [
                f"内蒙古师大的{major_name}在内蒙古教育领域地位重要。赛罕校区在林荫中环境不错。宿舍条件普通。食堂有蒙古族特色餐饮。就业以当老师为主。",
            ]
        elif '内蒙古科技' in name:
            opts = [
                f"内科大的{major_name}在包头，钢铁冶金特色鲜明。校园硬件在内蒙古算不错的。宿舍六人间。包头冬天冷但暖气好。就业在包钢等企业有优势。",
            ]
        else:
            opts = [f"在{name}读{major_name}，最大的感受就是冬天冷但室内暖气足。学校条件在内蒙古算正常水平，生活成本不高。"]
    
    # 新疆
    elif province == '新疆':
        if '新疆大学' in name:
            opts = [
                f"新大的{major_name}在新疆是顶级学府。211牌子在本省够用。校本部在市区交通便利。宿舍条件一般六人间。食堂有清真特色，大盘鸡和抓饭好吃。就业在新疆范围内认可度很高。",
                f"{name}的{major_name}以中亚研究为特色。多民族文化交流氛围浓厚。就是地理位置远，回家一趟不容易。宿舍条件普通。",
            ]
        elif '石河子' in name:
            opts = [
                f"石河子大学的{major_name}是新疆另一所211。校园绿化很好，石河子市本身是兵团城市很安全。宿舍条件一般。食堂价格便宜。就业在新疆及兵团系统很稳。",
            ]
        elif '新疆农业' in name:
            opts = [
                f"新疆农大的{major_name}依托新疆农业大区特色明显。校园在乌鲁木齐市区。宿舍条件普通。食堂清真餐饮为主。就业方向多为农业部门。",
            ]
        elif '新疆医科' in name:
            opts = [
                f"新疆医科大的{major_name}是新疆最好的医学院。教学医院资源丰富。宿舍条件一般。乌鲁木齐冬天冷夏天热。毕业后在新疆医疗系统很抢手。",
            ]
        elif '新疆师范' in name:
            opts = [
                f"新疆师大的{major_name}在新疆教育系统有影响力。校园在乌鲁木齐。宿舍条件普通。食堂有民族特色。就业以教师为主。",
            ]
        elif '喀什' in name:
            opts = [
                f"喀什大学的{major_name}位于南疆，地理位置独特。校园较新设施在改善。学生以少数民族为主，文化多元。条件相比乌鲁木齐艰苦一些。",
            ]
        elif '伊犁师范' in name:
            opts = [
                f"伊犁师范大学在伊宁，北疆气候相对温和。校园环境不错。宿舍条件一般。学{major_name}的话，当地对教师需求大。",
            ]
        else:
            opts = [f"在{name}读{major_name}，新疆地域广阔特色鲜明。学校条件虽然不如内地，但别有一番体验。饮食以清真为主。"]
    
    # 宁夏
    elif province == '宁夏':
        if '宁夏大学' in name:
            opts = [
                f"宁大的{major_name}是宁夏唯一的211。校园在银川西夏区，靠近西部影视城。宿舍条件一般。食堂有回族特色餐饮。银川城市不大但宜居。就业在宁夏足够用。",
            ]
        elif '北方民族' in name:
            opts = [
                f"北方民族大学的{major_name}在银川。多民族学生共处氛围独特。校园不算大但环境不错。宿舍条件普通。食堂清真特色。就业在宁夏及周边有基础。",
            ]
        elif '宁夏医科' in name:
            opts = [
                f"宁夏医科大的{major_name}是宁夏医学最高学府。临床教学资源在区内最好。宿舍条件一般。银川环境好空气干燥。毕业后在宁夏各大医院好就业。",
            ]
        else:
            opts = [f"在{name}读{major_name}，银川是塞上江南，环境比想象中好。学校条件一般但生活成本低。"]
    
    # 青海
    elif province == '青海':
        if '青海大学' in name:
            opts = [
                f"青大的{major_name}是青海唯一的211。清华对口支援力度大，部分课程共享清华资源。宿舍条件一般六人间。西宁夏天气候凉爽，避暑胜地。食堂牛羊肉多。就业在青海很稳。",
            ]
        elif '青海师范' in name:
            opts = [
                f"青海师大的{major_name}在西宁，高原师范特色。校园在市区生活方便。宿舍条件普通。西宁海拔两千多米，夏天不热。就业在青海教育系统地位不错。",
            ]
        elif '青海民族' in name:
            opts = [
                f"青海民族大学的{major_name}以民族学为特色。多民族学生共处文化多元。宿舍条件一般。西宁空气干燥但夏天凉快。",
            ]
        else:
            opts = [f"在{name}读{major_name}，高原环境需要适应。西宁城市节奏慢生活安逸。学校条件属于普通水平。"]
    
    # 西藏
    elif province == '西藏':
        if '西藏大学' in name:
            opts = [
                f"藏大的{major_name}在拉萨，高原特色鲜明。藏学、高原生态是王牌方向。学校硬件近年来改善很多。宿舍条件有提升但还是不如内地。拉萨紫外线强但夏天不热。食堂有藏餐特色，酥油茶和糌粑值得一试。包分配倾向明显，毕业基本留在西藏。",
            ]
        elif '西藏农牧' in name:
            opts = [
                f"西藏农牧学院在林芝，海拔比拉萨低气候更舒适。{major_name}结合高原农牧业特色。校园自然环境优美。条件相对艰苦但有一种原始的美。",
            ]
        else:
            opts = [f"在{name}读{major_name}，西藏是最特殊的体验。高原反应要适应一段时间。学校条件虽然有限但国家对西藏教育投入很大。"]
    
    # 甘肃
    elif province == '甘肃':
        if '兰州大学' in name:
            opts = [
                f"兰大的{major_name}是一所被地理位置低估的985。学术底蕴深厚，草学、化学等专业全国前列。宿舍条件在985中算差的，六人间无独卫。榆中校区比较偏远。食堂有牛肉面，味道正宗。学风朴实，适合潜心学术。",
                f"{name}的{major_name}学风扎实，学生吃苦耐劳。萃英学院拔尖培养很好。就是兰州气候干燥，春秋沙尘多。榆中校区去市区不方便。就业方面校友遍布科研院所。",
            ]
        elif '西北师范' in name:
            opts = [
                f"西北师大的{major_name}在西北地区师范院校中地位高。校园在安宁区环境清幽。宿舍条件一般。食堂牛肉面一绝。就业以西北地区教师为主。",
            ]
        elif '兰州理工' in name:
            opts = [
                f"兰州理工的{major_name}在甘肃工科里排前列。土木机械专业强。宿舍条件普通。食堂价格便宜。就业在甘肃的工业企业有口碑。",
            ]
        elif '兰州交通' in name:
            opts = [
                f"兰州交大的{major_name}在轨道交通领域有特色。毕业生进铁路系统很有优势。宿舍条件一般。食堂便宜管饱。就业在铁路系统很稳。",
            ]
        elif '甘肃农业' in name:
            opts = [
                f"甘肃农大的{major_name}以旱作农业为特色。校园在兰州营门滩。宿舍条件普通。食堂西北面食丰富。就业以农业技术推广为主。",
            ]
        elif '天水师范' in name:
            opts = [
                f"天水师范学院的{major_name}在天水市。校园环境不错，天水气候在甘肃算好的。宿舍条件一般。就业以甘肃基层教师为主。",
            ]
        else:
            opts = [f"在{name}读{major_name}，甘肃高校整体风格朴实。兰州牛肉面是日常。学校条件虽一般但学风扎实。"]
    
    # 贵州
    elif province == '贵州':
        if '贵州大学' in name:
            opts = [
                f"贵大的{major_name}作为贵州唯一的211，省内地位没得说。花溪校区周边环境好靠近湿地公园。宿舍条件四人间有独卫。食堂有贵州特色酸汤系列。就业在贵州足够用。",
                f"{name}的{major_name}在西南地区有一定知名度。校园面积大，绿化好。贵阳气候夏天凉快不需要空调。就是就业方面想去一线城市难度大。",
            ]
        elif '贵州师范' in name:
            opts = [
                f"贵州师大的{major_name}在贵阳宝山校区，交通便利。学{major_name}的话文科氛围好。宿舍条件普通。贵阳气候宜人夏天不热。就业以贵州教育系统为主。",
            ]
        elif '贵州医科' in name:
            opts = [
                f"贵州医科大的{major_name}是贵州医学教育的老牌。附属医院资源丰富。宿舍条件一般六人间。贵阳气候凉爽适合学医。毕业后在贵州医疗系统竞争力强。",
            ]
        elif '贵州理工' in name:
            opts = [
                f"贵州理工学院的{major_name}是新建工科院校。校园新设施较新。宿舍条件不错。贵阳气候好。虽然年轻但发展势头不错。",
            ]
        elif '遵义医科' in name:
            opts = [
                f"遵义医科大的{major_name}在遵义，红色名城。临床教学管理严格。宿舍条件一般。遵义生活成本低。毕业生在贵州医疗系统口碑好。",
            ]
        else:
            opts = [f"在{name}读{major_name}，贵阳夏天凉快是最大福利。学校条件中规中矩，生活成本不高。"]
    
    else:
        opts = [f"在{name}读{major_name}，整体体验中规中矩。学校条件属于普通水平。"]
    
    return random.choice(opts)

# ============================================================
# 生成分类评分和标签
# ============================================================

def generate_scores_and_tags(school, major_cat):
    """生成分类评分、总评分和标签"""
    province = school['province']
    adj = ADJUSTMENTS.get(province, {})
    level_adj = LEVEL_ADJ.get(school['level'], 0.0)
    
    # 基础评分（随机波动后）
    base = {
        'academic': round(random.uniform(2.5, 4.2), 2),
        'dormitory': round(random.uniform(2.0, 3.8), 2),
        'cafeteria': round(random.uniform(2.5, 4.0), 2),
        'cost': round(random.uniform(2.5, 4.0), 2),
        'environment': round(random.uniform(2.5, 4.0), 2),
        'employment': round(random.uniform(2.0, 3.8), 2),
        'admin': round(random.uniform(2.0, 3.5), 2),
        'mental': round(random.uniform(2.5, 4.0), 2),
    }
    
    # 对211/985学校提升学术分
    if '985' in school['level']:
        base['academic'] = round(random.uniform(4.0, 5.0), 2)
    elif '211' in school['level']:
        base['academic'] = round(random.uniform(3.5, 4.5), 2)
    elif '双一流' in school['level']:
        base['academic'] = round(random.uniform(3.0, 4.2), 2)
    
    # 特殊调整
    if province == '云南':
        base['environment'] = round(base['environment'] + 0.3, 2)
        base['cafeteria'] = round(base['cafeteria'] + 0.2, 2)
        base['employment'] = round(base['employment'] - 0.1, 2)
    elif province in ['内蒙古', '新疆', '宁夏', '青海', '西藏', '甘肃']:
        base['dormitory'] = round(base['dormitory'] - 0.2, 2)
        base['cafeteria'] = round(base['cafeteria'] - 0.1, 2)
        base['employment'] = round(base['employment'] - 0.2, 2)
    elif province == '海南':
        base['dormitory'] = round(base['dormitory'] + 0.1, 2)
        base['cafeteria'] = round(base['cafeteria'] + 0.1, 2)
        base['environment'] = round(base['environment'] + 0.2, 2)
    
    # 限幅
    for k in base:
        base[k] = max(1.0, min(5.0, base[k]))
        base[k] = round(base[k], 2)
    
    # 总评分（加权）
    weights = {'academic': 15, 'dormitory': 25, 'cafeteria': 15, 'cost': 10,
               'environment': 8, 'employment': 20, 'admin': 5, 'mental': 2}
    total_weight = sum(weights.values())
    overall = sum(base[k] * weights[k] for k in base) / total_weight
    overall = round(overall + level_adj, 2)
    overall = max(1.0, min(5.0, overall))
    
    # 标签
    tag_pool = []
    if base['dormitory'] >= 3.5:
        tag_pool.append('宿舍豪华')
    elif base['dormitory'] <= 2.5:
        tag_pool.append('宿舍破旧')
    
    if base['cafeteria'] >= 3.8:
        tag_pool.append('食堂神仙')
    elif base['cafeteria'] <= 2.5:
        tag_pool.append('食堂地狱')
    
    if base['environment'] >= 4.0:
        tag_pool.append('校园巨美')
    elif base['environment'] <= 2.5:
        tag_pool.append('校园荒凉')
    
    if base['employment'] >= 4.0:
        tag_pool.append('就业无忧')
    elif base['employment'] <= 2.5:
        tag_pool.append('就业困难')
    
    if base['academic'] >= 4.0:
        tag_pool.append('老师超好')
    
    if random.random() < 0.3:
        tag_pool.append('形式主义')
    if random.random() < 0.2:
        tag_pool.append('内卷严重')
    
    if len(tag_pool) < 1:
        tag_pool.append('佛系养身')
    
    tags = random.sample(tag_pool, min(3, len(tag_pool)))
    
    return base, overall, tags


# ============================================================
# 主生成循环
# ============================================================
all_reviews = []
dev_seq = next_seq

for school in target_schools:
    # 每所学校生成2-3条评价
    num_reviews = 2
    if school['level'] in ['985/211', '211']:
        num_reviews = 3
    
    matched = select_majors_for_school(school, num_reviews)
    
    for mid, mname, mcat in matched:
        dev_id = f"ai-generator-west-{dev_seq}"
        dev_seq += 1
        
        comment = gen_comment(school, mname, mcat)
        cat_scores, overall, tags = generate_scores_and_tags(school, mcat)
        
        all_reviews.append({
            'school_id': school['id'],
            'major_id': mid,
            'device_id': dev_id,
            'comment': comment,
            'overall_score': overall,
            'category_scores': json.dumps(cat_scores, ensure_ascii=False),
            'tags': json.dumps(tags, ensure_ascii=False),
        })

print(f"\nTotal reviews to insert: {len(all_reviews)}")

# ============================================================
# 插入数据库
# ============================================================
insert_count = 0
for r in all_reviews:
    try:
        cur.execute('''
            INSERT INTO reviews (school_id, major_id, device_id, answers, category_scores, overall_score, comment, tags)
            VALUES (?, ?, ?, '{}', ?, ?, ?, ?)
        ''', (
            r['school_id'], r['major_id'], r['device_id'],
            r['category_scores'], r['overall_score'],
            r['comment'], r['tags']
        ))
        insert_count += 1
    except Exception as e:
        print(f"Error inserting review for school {r['school_id']}, major {r['major_id']}: {e}")

conn.commit()
conn.close()

print(f"\n{'='*60}")
print(f"Successfully inserted {insert_count} reviews")
print(f"{'='*60}")

# Print summary table
print(f"\nSummary:")
print(f"{'School':<24} {'Province':<6} {'Type':<6} {'Reviews':<8}")
print(f"{'-'*50}")
for school in target_schools:
    school_reviews = [r for r in all_reviews if r['school_id'] == school['id']]
    print(f"{school['name']:<24} {school['province']:<6} {school['type']:<6} {len(school_reviews):<8}")

print(f"\nDevice IDs used: ai-generator-west-{next_seq} to ai-generator-west-{dev_seq-1}")
