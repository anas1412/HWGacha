"""Scan images/ for new photos. Cards listed in seed.json keep their curated name and rarity;
anything else gets a weighted dice roll and a name from the lists below."""
import json
import logging
import os
import random

import db
from config import IMAGES_DIR, RARITIES

log = logging.getLogger("scanner")

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
SEED_FILE = "seed.json"

# Card titles. Higher tiers pull from the more dramatic lists first.
TITLES = {
    "عادية": [
        "هيفاء الصباح", "لقطة عفوية", "ابتسامة خفيفة", "هيفاء على الطبيعة", "نظرة سريعة",
        "يوم عادي مع الملكة", "هيفاء بالكاجوال", "لحظة هدوء", "همسة الظهيرة", "هيفاء بلا فلتر",
        "قهوة الصباح", "طلة بسيطة", "هيفاء في الشارع", "سيلفي الملكة", "لقطة من بعيد",
    ],
    "مميزة": [
        "لمسة أنوثة", "نظرة الواوا", "هيفاء بالأحمر", "طلة المساء", "ضحكة ياباي",
        "هيفاء بالأسود", "غمزة الملكة", "طلة الكاميرا", "سحر اللبنانية", "بوسة للجمهور",
        "هيفاء بالذهبي", "نظرة جانبية", "ألق الغروب", "هيفاء والورد", "لمعة العيون",
    ],
    "نادرة": [
        "ملكة المسرح", "أضواء بيروت", "هيفاء تحت الأضواء", "بوس الواوا", "نجمة الحفل",
        "سحر الشرق", "ليلة الفستان الأبيض", "هيفاء والميكروفون", "نظرة تذيب القلوب", "أيقونة الجمال",
        "طلة السجادة الحمراء", "هيفاء بالفضي", "رقصة الضوء", "لهيب المسرح", "أميرة الليل",
    ],
    "أسطورية": [
        "الوعوع الأسطورية", "ملكة الإغراء", "طلة القرن", "هيفاء الأيقونة", "ليلة الجوائز",
        "أسطورة الشاشة", "تاج الجمال العربي", "نجمة لا تنطفئ", "هيفاء في أبهى حللها", "ملكة السجادة",
        "سيدة الأضواء", "الفستان الذي أوقف الحفل", "هيفاء الخالدة", "جمال لا يُنسى", "طلة العمر",
    ],
    "الملكة": [
        "الملكة", "هيفاء وهبي", "أنا هيفاء", "الملكة المتوّجة", "أسطورة لبنان",
        "ملكة الملكات", "الطلة الخالدة", "لحظة التاريخ", "تاج الشرق", "الملكة بلا منازع",
    ],
}

DESCRIPTIONS = {
    "عادية": ["لقطة عادية بس الملكة ما بتكون عادية أبداً.", "يوم من أيام هيفاء.", "بسيطة وحلوة."],
    "مميزة": ["فيها شي مميز... شو هو؟ شوف بنفسك.", "طلة لطيفة تخطف النظر.", "نظرة واحدة وبتفهم."],
    "نادرة": ["ما بتشوفها كل يوم.", "لقطة نادرة لملكة الطلات.", "احتفظ بها، صعب تلاقي مثلها."],
    "أسطورية": ["لحظة دخلت التاريخ.", "طلة حكى عنها الكل.", "الأسطورة بشخصها."],
    "الملكة": ["👑 الملكة فقط. لا تعليق.", "أندر ما يمكن أن تملكه.", "هيفاء في أعلى مراتب المجد."],
}


def _pick_name(rarity, taken):
    candidates = [t for t in TITLES[rarity] if t not in taken]
    if candidates:
        return random.choice(candidates)
    base = random.choice(TITLES[rarity])
    n = 2
    while f"{base} {n}" in taken:
        n += 1
    return f"{base} {n}"


async def scan_new_images():
    """Register every image in images/ that isn't in the DB yet. Returns (new_cards, failed_files)."""
    known = db.known_files()
    taken = set(db.all_names())
    new = []
    tiers = list(RARITIES)
    weights = [RARITIES[t]["weight"] for t in tiers]
    seed = {}
    if os.path.exists(SEED_FILE):
        with open(SEED_FILE, encoding="utf-8") as f:
            seed = {c["file"]: c for c in json.load(f)}
    for file in sorted(os.listdir(IMAGES_DIR)):
        if os.path.splitext(file)[1].lower() not in IMAGE_EXTS or file in known:
            continue
        if file in seed:
            rarity, name, desc = seed[file]["rarity"], seed[file]["name"], seed[file]["description"]
            if name in taken:
                name = _pick_name(rarity, taken)
        else:
            rarity = random.choices(tiers, weights=weights)[0]
            name = _pick_name(rarity, taken)
            desc = random.choice(DESCRIPTIONS[rarity])
        taken.add(name)
        card_id = db.add_card(file, name, rarity, desc)
        new.append(db.get_card(card_id))
        log.info("card %s -> %s [%s]", file, name, rarity)
    return new, []
