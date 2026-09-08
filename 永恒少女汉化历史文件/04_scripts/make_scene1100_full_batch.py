#!/usr/bin/env python3
"""Generate scene 1100 from perfect v2 alignment plus reviewed Chinese polish."""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERIC = ROOT / "04_scripts" / "make_translation_batch.py"
ALIGNMENT = ROOT / "03_text" / "matched" / "pc-ns-alignment-candidates-v2.tsv"
NS_EXTRACT = ROOT / "03_text" / "ns_extracted" / "ns-strings-v1.0.3.tsv"
OUTPUT = ROOT / "03_text" / "translated" / "scene1100-full-v1.tsv"


POLISH: dict[int, tuple[str, str]] = {
    1: ("她已经记不清自己究竟绕过哪些地方、又是怎么走的了，只觉得同样的景色似乎看过好几次。", "fix どこをどう回ったのか nuance"),
    8: ("@vv40503「胆子真大呢。总之，找到你就好」", "render 大胆 as bold rather than brave"),
    14: ("@vv40506「这所学园名叫『普埃拉利姆』。这里是培养『少女』，让她们为人们创造更美好生活的地方」", "remove unnecessary PC Latin ruby and smooth term explanation"),
    15: ("『普埃拉利姆』这个名字，露珂已经在钟塔告诉过她；『少女』这个词，她也听过好几次。不过，能像这样重新听人仔细说明，还是让她很感激。", "standardize terms without PC Latin ruby"),
    16: ("@vv00903「阿德拉老师说过吧。『少女』当然是越多越好，对这个世界来说，培养少女是当务之急」", "standardize Maiden term"),
    17: ("@vv40507「之前也说过，不是谁都能成为少女的。必须具备相应的资质」", "standardize Maiden term and 素質 wording"),
    26: ("@vv00906「连这种事都能做到吗？」", "natural dialogue"),
    34: ("阿尔艾特茫然地反复默念着刚刚听到的词。", "avoid literal Chinese 反刍"),
    36: ("@vv40514「但是，『少女的王座』不会自己判断该造化什么。必须有人作出判断，在脑中想象出详细的样子，再把这些信息传达给它」", "natural explanation and restore agent"),
    70: ("阿尔艾特发出一声赞叹的叹息。", "fix awkward 赞叹地叹了口气"),
    77: ("不经意间，她的视线突然被那朵花吸引，发现它的瞬间便再也移不开了。", "remove unnecessary PC emphasis ruby"),
    82: ("那朵蔷薇蕴藏着与其他花截然不同的奇异光辉。与其说是阳光透过花瓣，不如说光是从花本身发出的，带着如冰或宝石般冷硬的质感。", "natural rendering of 硬質な光"),
    97: ("阿尔艾特不禁发出一声赞叹。", "fix awkward 惊声叹了口气"),
    103: ("阿尔艾特把目光投向外侧墙体内凹的通道。那里已经看不到先前那头火焰般的红发。", "fix recurring 外辺部 spatial mistranslation"),
    110: ("@vv00923「哦……」", "render へぇ naturally"),
    113: ("她投向书本的金色目光充满热情，甚至称得上近乎凶猛。", "avoid 狰狞 mistranslation of 獰猛"),
    114: ("她的本性恐怕称不上品行端正，却能在必要时不露破绽地圆滑行事。在如此严苛的环境里还能维持体面外表，这份强韧与机敏反倒相当可靠。", "restore positive 頼もしい強かさ nuance"),
    115: ("不过，比起这些，阿尔艾特更在意另一件事──萝宾偶尔会对卡娜莉显露出的尖锐态度。", "fix 険 mistranslation as bad-mouthing"),
    123: ("@vv40538「我总觉得，就算被萝宾讨厌也是没办法的事。奇怪的是，我自己还很能接受这一点」", "natural dialogue"),
    128: ("栗色发丝间露出的肌肤显得越发苍白，与那纤弱的容貌相衬，宛如一幅幽愁的画。", "fix Chinese classifier and prose"),
    129: ("她说得像是已经想开了，可在阿尔艾特看来，萝宾朝她刺来的那些尖锐态度，依然实实在在地折磨着卡娜莉。", "fix 割り切った nuance"),
    133: ("走廊笔直向前延伸，脚步声在高高的天花板下清晰回荡。", "fix grammar/acoustics"),
    134: ("走廊一侧排列着装有玻璃的门。听卡娜莉说，特进班真正需要用到的房间其实很有限。", "fix 用のある nuance"),
    142: ("宽阔的空间里铺设着大量管道，还有发出微弱低鸣的大木箱，整体结构与造化室相同。", "translate 配管 and smooth narration"),
    143: ("不同的是，中央原本放置玻璃罩与椅子的位置，换成了一台巨大的装置。", "fix singular 巨大な装置"),
    145: ("@vv40544「在座学室里，可以用装置阅览资料。这些资料做得非常精良……你一定会吃惊的」", "fix 的/得 and natural dialogue"),
    148: ("@vv00930「嗯，你这么一说，我就更想知道了」", "natural dialogue"),
    154: ("阿尔艾特告诉卡娜莉，自己已经用过造化室一次，不必再介绍了。卡娜莉似乎也一直担心会打扰里面的人，听她这么说便放心地点头答应。", "smooth narration"),
    156: ("@vv00933「可惜，她很快就发现了我，然后让那朵蔷薇枯萎了……」", "render 枯らす rather than generic destroy"),
    157: ("阿尔艾特原本想说得平淡些，可心中的阴影还是渗进了声音里。要是先前开门前也像现在这样观察一下里面，就不会有那场不幸的相遇了。", "fix awkward narration"),
    158: ("@vv40547「……你没事吧？　她有没有对你说什么？」", "avoid 有被 construction"),
    160: ("@vv40548「确实很像。阿薇拉她……该怎么说呢，总是在拼命逼着自己」", "natural 必死 nuance"),
    166: ("@vv40550「她虽然很有自信，却始终绷紧着神经。因为不知道什么时候会被别人超越，而对她来说，那是绝对不能发生的事」", "fix 気を張っている mistranslation"),
    167: ("@vv40551「阿薇拉比任何人都认真地以『永恒少女』为目标」", "remove unnecessary PC Latin ruby"),
    178: ("能让一条与当时整体风向相反的意见被采纳，本身就说明露珂拥有足够的发言权。就连钢铁般冷硬的阿德拉，似乎也对她另眼相看。", "replace awkward 逆流而行 metaphor"),
    181: ("@vv40556「是的。后面依次是萝宾、我、玛可、帕沃妮」", "make ranking order explicit"),
    185: ("@vv40558「检测时的数值只要超过基准，就一定会进入特进班。你的成绩可是远远超过了基准」", "fix 超过数值 wording"),
    189: ("@vv40560「你的前两项也很出色，但我觉得尤其突出的是多样性。一般来说，适性检测阶段根本没办法同时让多朵花绽放」", "fix 複数の花 mistranslation as multiple types"),
    193: ("@vv40562「咦？　……啊。从你的角度看，是在一个完全陌生的地方，突然按照自己根本不熟悉的价值观被捧得这么高啊」", "restore core meaning omitted by PC translation"),
    202: ("@vv40565「但是，大家应该都想摆脱自己那些丑陋的感情。而且总有一天，我们一定能做到」", "clarify referent of 実現できる"),
    203: ("@vv40566「也许需要一些时间。但在那之前，我会尽我所能，不让你遭遇不愉快的事……」", "restore proactive meaning of 厭な思いをしないよう"),
    209: ("阿尔艾特道谢后，卡娜莉像一朵柔弱的花般微笑。阿尔艾特在心里暗暗发誓，尽量不要再让这个胆怯的少女为自己操心。", "soften overly harsh 怯懦 and smooth ending"),
}


def main() -> int:
    subprocess.run(
        [
            sys.executable,
            str(GENERIC),
            str(ALIGNMENT),
            str(NS_EXTRACT),
            "--scene", "1100",
            "--start", "0",
            "--end", "209",
            "--output", str(OUTPUT),
        ],
        check=True,
    )

    with OUTPUT.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        fields = list(reader.fieldnames or [])
        rows = list(reader)

    if len(rows) != 210 or [int(r["ns_filtered_index"]) for r in rows] != list(range(210)):
        raise ValueError("scene 1100 generic batch is not contiguous 0..209")

    for idx, (translation, note) in POLISH.items():
        row = rows[idx]
        row["translation"] = translation
        row["alignment_status"] = "manual-reviewed-polish"
        row["alignment_reason"] = note

    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    print("scene=1100")
    print(f"rows_written={len(rows)}")
    print(f"manual_polishes={len(POLISH)}")
    print(f"output={OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
