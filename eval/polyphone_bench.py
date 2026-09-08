# -*- coding: utf-8 -*-
"""多音字词级消歧评测：天神（形+音词表）vs pypinyin。

测试集：常见多音字词，每个词在词级语境下有唯一标准读音（数字调号）。
公平性：双方都做词级注音（我们用 CEDICT 词表 + 汉字读音兜底；
pypinyin 用其内置词组词典 + 单字词典），逐词比较音节+声调。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.pinyin.annotate import annotate_word  # noqa: E402
from src.pinyin.cedict import load_cedict  # noqa: E402

# 测试集：词 → 正确读音（数字调号，轻声用 5 省略约定与 pypinyin 一致）
TEST_SET: dict[str, str] = {
    # 行
    "银行": "yin2 hang2", "行走": "xing2 zou3", "行列": "hang2 lie4",
    "行业": "hang2 ye4", "自行车": "zi4 xing2 che1",
    # 长
    "长大": "zhang3 da4", "长城": "chang2 cheng2", "校长": "xiao4 zhang3",
    "长短": "chang2 duan3",
    # 乐
    "音乐": "yin1 yue4", "快乐": "kuai4 le4", "乐队": "yue4 dui4",
    # 重
    "重要": "zhong4 yao4", "重新": "chong2 xin1", "重庆": "chong2 qing4",
    "重量": "zhong4 liang4",
    # 都
    "首都": "shou3 du1", "都是": "dou1 shi4",
    # 得/地/的（轻声）
    "觉得": "jue2 de5", "我的": "wo3 de5", "慢慢地": "man4 man4 de5",
    "得到": "de2 dao4",
    # 还
    "还是": "hai2 shi4", "还书": "huan2 shu1",
    # 教
    "教师": "jiao4 shi1", "教书": "jiao1 shu1",
    # 觉
    "睡觉": "shui4 jiao4", "觉得": "jue2 de5", "觉醒": "jue2 xing3",
    # 假
    "放假": "fang4 jia4", "真假": "zhen1 jia3",
    # 间
    "时间": "shi2 jian1", "间谍": "jian4 die2",
    # 发
    "头发": "tou2 fa5", "发现": "fa1 xian4",
    # 干
    "干净": "gan1 jing4", "干活": "gan4 huo2",
    # 好
    "好人": "hao3 ren2", "爱好": "ai4 hao4",
    # 会
    "会议": "hui4 yi4", "会计": "kuai4 ji4",
    # 几
    "几个": "ji3 ge4", "茶几": "cha2 ji1",
    # 看
    "看见": "kan4 jian4", "看护": "kan1 hu4",
    # 空
    "天空": "tian1 kong1", "空白": "kong4 bai2",
    # 难
    "困难": "kun4 nan2", "灾难": "zai1 nan4",
    # 强
    "强大": "qiang2 da4", "勉强": "mian3 qiang3", "倔强": "jue2 jiang4",
    # 省
    "节省": "jie2 sheng3", "反省": "fan3 xing3",
    # 数
    "数学": "shu4 xue2", "数数": "shu3 shu4",
    # 调
    "调查": "diao4 cha2", "调整": "tiao2 zheng3", "声调": "sheng1 diao4",
    # 为
    "因为": "yin1 wei4", "为了": "wei4 le5", "成为": "cheng2 wei2",
    # 相
    "互相": "hu4 xiang1", "照相": "zhao4 xiang4",
    # 兴
    "高兴": "gao1 xing4", "兴奋": "xing1 fen4",
    # 应
    "应该": "ying1 gai1", "应答": "ying4 da2",
    # 与
    "与其": "yu3 qi2", "参与": "can1 yu4",
    # 中
    "中国": "zhong1 guo2", "中奖": "zhong4 jiang3",
    # 种
    "种子": "zhong3 zi5", "种地": "zhong4 di4",
    # 传
    "传说": "chuan2 shuo1", "自传": "zi4 zhuan4",
    # 便
    "方便": "fang1 bian4", "便宜": "pian2 yi5",
    # 朝
    "朝霞": "zhao1 xia2", "朝代": "chao2 dai4",
    # 称
    "称呼": "cheng1 hu1", "对称": "dui4 chen4",
    # 处
    "处理": "chu3 li3", "到处": "dao4 chu4",
    # 弹
    "弹琴": "tan2 qin2", "子弹": "zi3 dan4",
    # 当
    "当时": "dang1 shi2", "上当": "shang4 dang4",
    # 倒
    "倒下": "dao3 xia4", "倒水": "dao4 shui3",
    # 分
    "分开": "fen1 kai1", "水分": "shui3 fen4",
    # 更
    "更加": "geng4 jia1", "三更": "san1 geng1",
    # 和
    "和平": "he2 ping2", "附和": "fu4 he4", "和面": "huo2 mian4", "暖和": "nuan3 huo5",
    # 划
    "计划": "ji4 hua4", "划船": "hua2 chuan2",
    # 将
    "将来": "jiang1 lai2", "将领": "jiang4 ling3",
    # 降
    "降落": "jiang4 luo4", "投降": "tou2 xiang2",
    # 尽
    "尽力": "jin4 li4", "尽管": "jin3 guan3",
    # 禁
    "禁止": "jin4 zhi3", "不禁": "bu4 jin1",
    # 卷
    "试卷": "shi4 juan4", "卷起": "juan3 qi3",
    # 累
    "劳累": "lao2 lei4", "积累": "ji1 lei3",
    # 量
    "数量": "shu4 liang4", "测量": "ce4 liang2",
    # 落
    "落下": "luo4 xia4", "落枕": "lao4 zhen3",
    # 没
    "没有": "mei2 you3", "淹没": "yan1 mo4",
    # 模
    "模型": "mo2 xing2", "模样": "mu2 yang4",
    # 宁
    "安宁": "an1 ning2", "宁可": "ning4 ke3",
    # 漂
    "漂亮": "piao4 liang5", "漂流": "piao1 liu2",
    # 铺
    "店铺": "dian4 pu4", "铺床": "pu1 chuang2",
    # 奇
    "奇怪": "qi2 guai4", "奇数": "ji1 shu4",
    # 切
    "一切": "yi1 qie4", "切开": "qie1 kai1",
    # 圈
    "圆圈": "yuan2 quan1", "羊圈": "yang2 juan4",
    # 散
    "散步": "san4 bu4", "散装": "san3 zhuang1",
    # 少
    "多少": "duo1 shao3", "少年": "shao4 nian2",
    # 舍
    "宿舍": "su4 she4", "舍弃": "she3 qi4",
    # 似
    "似乎": "si4 hu1", "似的": "shi4 de5",
    # 宿
    "宿舍": "su4 she4", "星宿": "xing1 xiu4", "一宿": "yi1 xiu3",
    # 校
    "学校": "xue2 xiao4", "校对": "jiao4 dui4",
    # 血
    "血液": "xue4 ye4", "流血": "liu2 xue4",
    # 咽
    "咽喉": "yan1 hou2", "吞咽": "tun1 yan4",
    # 要
    "重要": "zhong4 yao4", "要求": "yao1 qiu2",
    # 载
    "记载": "ji4 zai3", "载重": "zai4 zhong4",
    # 脏
    "肮脏": "ang1 zang1", "心脏": "xin1 zang4",
    # 扎
    "扎实": "zha1 shi5", "挣扎": "zheng1 zha2", "扎针": "zha1 zhen1",
    # 折
    "折断": "zhe2 duan4", "折腾": "zhe1 teng5",
    # 转
    "转身": "zhuan3 shen1", "转圈": "zhuan4 quan1",
    # 着
    "着急": "zhao2 ji2", "着落": "zhuo2 luo4", "看着": "kan4 zhe5",
    # 作
    "工作": "gong1 zuo4", "作坊": "zuo1 fang5",
    # 参
    "参加": "can1 jia1", "人参": "ren2 shen1",
    # 曾
    "曾经": "ceng2 jing1", "曾祖父": "zeng1 zu3 fu4",
    # 差
    "差别": "cha1 bie2", "差不多": "cha4 bu5 duo1", "出差": "chu1 chai1",
    # 待
    "等待": "deng3 dai4", "待会儿": "dai1 hui4 er5",
    # 担
    "担心": "dan1 xin1", "重担": "zhong4 dan4",
    # 逮
    "逮捕": "dai4 bu3", "逮住": "dai3 zhu4",
    # 藏
    "收藏": "shou1 cang2", "宝藏": "bao3 zang4",
    # 暴
    "暴露": "bao4 lu4",
    # 背
    "背包": "bei1 bao1", "背诵": "bei4 song4",
    # 薄
    "单薄": "dan1 bo2", "薄荷": "bo4 he5",
    # 臭
    "臭气": "chou4 qi4",
    # 处
    "处理": "chu3 li3", "到处": "dao4 chu4",
}


def _norm(reading: str) -> list[str]:
    """把读音串规范化为音节+声调列表（无数字补 5=轻声）。"""
    out = []
    for tok in reading.split():
        tok = tok.strip().lower()
        if not tok:
            continue
        if not tok[-1].isdigit():
            tok += "5"
        out.append(tok)
    return out


def main() -> int:
    import pypinyin
    from pypinyin import Style

    cedict = load_cedict()
    ours_ok = theirs_ok = 0
    rows: list[tuple[str, str, str, str, bool, bool]] = []
    for word, correct in TEST_SET.items():
        expected = _norm(correct)
        # 天神：词级标注
        entry = annotate_word(word, cedict)
        ours = _norm(entry["numbered"])
        # pypinyin：词组词典 + 单字词典
        try:
            theirs = _norm(" ".join(
                s for syl in pypinyin.pinyin(word, style=Style.TONE3, heteronym=False)
                for s in syl))
        except Exception:
            theirs = []
        ours_good = ours == expected
        theirs_good = theirs == expected
        ours_ok += ours_good
        theirs_ok += theirs_good
        rows.append((word, correct, entry["numbered"], " ".join(theirs),
                     ours_good, theirs_good))

    n = len(TEST_SET)
    print(f"多音词测试集: {n} 词")
    print(f"{'词':<6} {'正确':<16} {'天神':<16} {'pypinyin':<16} {'天神✓':<5} {'py✓'}")
    for word, correct, ours, theirs, og, tg in rows:
        if not og or not tg:  # 只打印双方不一致的行
            print(f"{word:<6} {correct:<16} {ours:<16} {theirs:<16} {'✓' if og else '✗':<5} {'✓' if tg else '✗'}")
    print(f"\n天神  准确率: {ours_ok}/{n} = {ours_ok/n:.1%}")
    print(f"pypinyin 准确率: {theirs_ok}/{n} = {theirs_ok/n:.1%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
