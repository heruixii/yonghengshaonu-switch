#!/usr/bin/env python3
"""Build authoritative scene batches from JP-v3 alignment plus direct NS translations."""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V3 = ROOT / "03_text" / "matched" / "pc-ns-alignment-v3-jp.tsv"
V2_SUMMARY = ROOT / "03_text" / "matched" / "scene-alignment-summary-v2.tsv"
NS_EXTRACT = ROOT / "03_text" / "ns_extracted" / "ns-strings-v1.0.3.tsv"
OLD_DIRECT = ROOT / "03_text" / "translated" / "bulk-post1100" / "exception-direct-translations.tsv"
NEW_DIRECT = ROOT / "03_text" / "translated" / "v3-new-direct-translations.tsv"
OUT_DIR = ROOT / "03_text" / "translated" / "v3-final-scenes"

VOICE_RE = re.compile(r"^(@v{2,3}[A-Za-z0-9]+)")
PC_RUBY_RE = re.compile(r"\|([^\[]+)\[([^\]]+)\]")
PC_RUBY_LEFT_RE = re.compile(r"\|[^\[]+\[[^\]]*\]")
KANA_RE = re.compile(r"[\u3040-\u30ff]")

FIXED_PC_RESIDUE: dict[tuple[str, int], str] = {
    ("1020", 194): "@vv50116「我再等你10秒钟。一、二——……」",
    ("1040", 114): "@vv00315「特进班……？」",
    # PC Chinese appends an unrelated sentence about the class erupting in noise.
    ("1130", 28): "即使尽量不去想坏事，想象却很容易滋生，还没来得及阻止便已经成形。",
    # PC Chinese GSC has raw strings 28/29 swapped relative to the original
    # Japanese GSC.  Keep the NS semantic order authoritative here.
    ("1160", 23): "突然，阿尔艾特眼前出现了一朵鲜红的蔷薇──『少女』。",
    ("1160", 24): "就在她眨眼闭上眼睛的那一瞬间，它便出现在了眼前。",
    ("2090", 42): "@vv71207「啊……怎么了，阿薇拉。@r不@·@@r高@·@@r兴@·@@r的@·@@r样@·@子」",
    ("2090", 54): "@vv71209「知——道——了……」",
    ("1280", 0): "就这样阿尔艾特度过了在普埃拉利姆的第三天。@n@p──本该如此。",
    ("1360", 23): "就这样，她一边追溯记忆一边吹出的口哨，像鸟鸣到了连本人都吃惊的程度。@k",
    # ^m is PC-only layout markup; preserve the Switch-side spacing instead.
    ("1410", 64): "　@n　　　　　　　　　　──没关系──",
    ("1420", 10): "@vv03404「我已经起来了。@k",
    ("1420", 74): "所以，没问题。@n@p恶之种绝不可能有蔓延的机会──",
    ("2200", 27): "──是露珂的声音。@n@p意识到这一点的瞬间，阿尔艾特一下子被拉回了现实。",
    ("2230", 39): "她就这样讽刺萝宾问了个『无聊的问题』，随后离开了。",
    # PC Chinese mistranslates 開き直る in the opposite direction here.
    ("2230", 42): "她甚至有些想索性就这么想开了。",
    ("2250", 25): "座学室里一个人也没有。明明既没听见脚步声，也没听见开门声。",
    ("2320", 139): "──明明一切都是幻觉。@n@p──明明嘴唇感受到的温度、吐息、声音和话语，都不过是自己擅自制造的想象。",
    # ^m is PC-only centered-line markup; keep the Switch full-width spacing.
    ("2340", 26): "　@n　　　　　　　　　　──玛可──",
    ("3010", 46): "看来我在无意识中把身体探到了危险的位置。好在最后关头及时停了下来，但目光仍被脚下的景色吸引。",
    ("3020", 31): "@vv05658「毕竟也不是能按自己的意愿选择的……@k",
    ("3060", 26): "@vv42306「萝宾……@k",
    # PC Chinese named アヴェルラ as 阿尔艾特 here.
    ("3110", 20): "舞台是普埃拉利姆，主人公则是自己。萝宾、露珂和阿薇拉等熟悉的面孔也会在梦里出现。",
    # PC Chinese reverses 怖くない (“less frightening / not frightening”).
    ("3160", 24): "也许是石板路被雾气遮住了，阿尔艾特觉得眼前的景象反而没有白天俯瞰时那么可怕。",
    # PC Chinese misreads emphasized あく (“opens”) as 没有 (“does not exist”).
    ("3210", 18): "@vv43005「如果那里@r会打开@··@的话，应该有什么地方藏着开关」",
    ("3200", 11): "@vv06203「在最神圣的地方有通往地狱的门，这种构想其实意外地很常见呢」",
    ("3220", 10): "@vv06254「阿薇拉，你为什么会在这里？@k",
    ("3230", 3): "@vv73401（原来还能做到这种事……@k",
    ("3270", 58): "原来你会这样装傻。@n@p──我终于正确理解了她眼中『卡娜莉』的形象，感觉仿佛被人从钟楼上推了下去。",
    # 汚す means to taint/deglamorize the idea, not erase the thought itself.
    ("3400", 35): "阿德拉用这样的说法，玷污了少女们多少都会抱有的、朦胧的求死念头，使其失去原本可能带有的诱惑。",
    ("4030", 47): "──又是这个名字──@p又来？",
    # PC Chinese reverses the conclusion: JP says thought alone cannot solve it.
    ("4040", 15): "露珂的处境和想法，要是光靠思考就能弄明白，早就已经得出结论了。到处都是矛盾与谜团，根本不可能就这样解决。",
    ("4170", 54): "应该花不了多少时间。这我知道。@n@p──可是。",
    ("4220", 69): "是否要为她而死──@e",
    # 手にかける means to kill by one's own hand here, not to seize/control.
    ("4250", 118): "一直以来，每当像这样亲手杀死异造化的学生之后，阿尔艾特都会被露珂毁灭。",
    ("4250", 34): "那声音仿佛渗出了十足的『人类』脆弱。@n@p真刺耳。",
    ("4270", 185): "最后的一句话是──@e",
    ("4300", 172): "@vv61559「毕竟她不仅公然违反规定，愿望还是『想让花开起来』。我甚至一度猜想，她是不是把这里错当成造化室才误闯进来的」",
    # The JP says the subjects likely did not even understand that the treatment
    # itself was humiliating; the PC line changed that into a different claim.
    ("4300", 143): "@vv07630「……被欺骗，以及她们恐怕连自己正受到屈辱性的对待都没有意识到。换作这种处境，确实会让人想抛下职责吧」",
    ("4330", 2): "应该调查哪里──@e",
    # Passive 飽きられていた refers to the rumor having grown stale generally,
    # not the first-person narrator personally getting tired of it.
    ("4430", 96): "到了那时，关于『肉之子』的传闻早已被大家听腻了。",
    # PC Chinese reverses 得やすい: the JP says created beings obtain Siman most easily.
    ("4410", 56): "@vv23006「没有什么比造化物更容易获得『@r智见种@希曼@』了。尤其是@r人造人@霍姆雷姆@」",
    ("4420", 19): "那幅画宛如超脱尘世的理想乡，甚至让人觉得，也许这样的地方真的存在于世界某处。",
    # 家畜を食肉と呼ぶ = referring to livestock as meat, not a feeding cry.
    ("4420", 25): "不，对他们而言这恐怕连蔑称都算不上，就像把家畜称作『食用肉』一样吧。",
}


def convert_pc(ns_source: str, pc_cn: str) -> str:
    text = pc_cn.replace("^n", "@n")
    text = PC_RUBY_RE.sub(lambda m: f"@r{m.group(1)}@{m.group(2)}@", text)
    if PC_RUBY_LEFT_RE.search(text):
        raise ValueError(f"unconverted PC ruby: {pc_cn!r}")
    voice = VOICE_RE.match(ns_source)
    if voice and not text.startswith(voice.group(1)):
        text = voice.group(1) + text
    return text


def load_direct(path: Path) -> dict[tuple[str, int], str]:
    out = {}
    if not path.exists():
        return out
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            out[(r["scene"], int(r["ns_filtered_index"]))] = r["translation"]
    return out


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    targets = {}
    with V2_SUMMARY.open("r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["scene"].isdigit() and 1010 <= int(r["scene"]) < 5000 and int(r["ns_story_tokens"]) > 0:
                targets[r["scene"]] = int(r["ns_story_tokens"])

    ns_meta = {}
    with NS_EXTRACT.open("r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            ns_meta[(r["file"], r["length_offset"])] = r

    by_scene: dict[str, dict[int, dict[str, str]]] = defaultdict(dict)
    with V3.open("r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["scene"] not in targets or not r["ns_filtered_index"]:
                continue
            idx = int(r["ns_filtered_index"])
            by_scene[r["scene"]][idx] = r

    direct = load_direct(OLD_DIRECT)
    direct.update(load_direct(NEW_DIRECT))

    fields = [
        "file", "length_offset", "text_offset", "stored_length", "byte_length",
        "source", "translation", "scene", "ns_filtered_index", "pc_file",
        "pc_string_index", "alignment_status", "alignment_reason",
    ]
    total = pc_rows = direct_rows = 0
    kana_rows = voice_mismatch = 0
    missing_direct = []

    for scene, expected in sorted(targets.items(), key=lambda x: int(x[0])):
        amap = by_scene.get(scene, {})
        if set(amap) != set(range(expected)):
            raise ValueError(f"scene {scene}: v3 NS indices mismatch expected={expected} got={len(amap)}")
        rows = []
        for idx in range(expected):
            a = amap[idx]
            source = a["ns_source"]
            key = (scene, idx)
            if a["status"] in ("exact-jp", "high-jp"):
                translation = convert_pc(source, a["pc_translation"])
                translation = FIXED_PC_RESIDUE.get(key, translation)
                status = a["status"]
                reason = f"PC JP->NS JP verified similarity={a['similarity']}"
                pc_file = a["pc_file"]
                pc_string_index = a["pc_string_index"]
                pc_rows += 1
            else:
                if key not in direct:
                    missing_direct.append(key)
                    continue
                translation = direct[key]
                status = "manual-direct-v3"
                reason = f"v3 status={a['status']} similarity={a['similarity']}; translated from NS source"
                pc_file = ""
                pc_string_index = ""
                direct_rows += 1

            meta = ns_meta[(a["ns_file"], a["ns_length_offset"])]
            sv = VOICE_RE.match(source)
            tv = VOICE_RE.match(translation)
            if (sv.group(1) if sv else None) != (tv.group(1) if tv else None):
                voice_mismatch += 1
            if KANA_RE.search(translation):
                kana_rows += 1
            rows.append({
                "file": meta["file"], "length_offset": meta["length_offset"],
                "text_offset": meta["text_offset"], "stored_length": meta["stored_length"],
                "byte_length": meta["byte_length"], "source": source,
                "translation": translation, "scene": scene,
                "ns_filtered_index": str(idx), "pc_file": pc_file,
                "pc_string_index": pc_string_index, "alignment_status": status,
                "alignment_reason": reason,
            })
        if len(rows) != expected:
            continue
        p = OUT_DIR / f"scene{scene}-full-v3.tsv"
        with p.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields, delimiter="\t", lineterminator="\n")
            w.writeheader(); w.writerows(rows)
        total += len(rows)

    if missing_direct:
        raise ValueError(f"missing direct translations ({len(missing_direct)}): {missing_direct[:80]}")
    print(f"scenes={len(targets)}")
    print(f"rows={total}")
    print(f"pc_verified_rows={pc_rows}")
    print(f"direct_rows={direct_rows}")
    print(f"voice_mismatch={voice_mismatch}")
    print(f"translation_kana_rows={kana_rows}")
    print(f"output_dir={OUT_DIR}")
    if voice_mismatch or kana_rows:
        raise SystemExit(2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
