"""
요한계시록 암기 훈련 텔레그램 봇
- polling 방식
- 더미 웹서버 (헬스체크)
- Firebase Firestore 연동
- 텔레그램 ID 기준 자동 로그인 (webapp ?uid=)
"""

import os
import json
import time
import logging
import threading
import http.server
import socketserver
import requests

import firebase_admin
from firebase_admin import credentials, firestore

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ─────────────── 설정 ───────────────
TOKEN = os.environ["TELEGRAM_TOKEN"]
WEBAPP_URL = os.environ["WEBAPP_URL"].rstrip("/")

GROUPS = ["부녀회", "장년회", "청년회", "자문회", "교역자"]

logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)

# ─────────────── Firebase 초기화 ───────────────
_key_dict = json.loads(os.environ["FIREBASE_KEY_JSON"])
_cred = credentials.Certificate(_key_dict)
firebase_admin.initialize_app(_cred)
db = firestore.client()


# ─────────────── 키보드 ───────────────
def group_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👩 부녀회", callback_data="grp:부녀회"),
         InlineKeyboardButton("👨 장년회", callback_data="grp:장년회")],
        [InlineKeyboardButton("🧑 청년회", callback_data="grp:청년회"),
         InlineKeyboardButton("💼 자문회", callback_data="grp:자문회")],
        [InlineKeyboardButton("⛪ 교역자", callback_data="grp:교역자")],
    ])


def youth_bu_keyboard():
    """청년회 부 선택"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1부", callback_data="ybu:1부"),
         InlineKeyboardButton("2부", callback_data="ybu:2부"),
         InlineKeyboardButton("3부", callback_data="ybu:3부"),
         InlineKeyboardButton("4부", callback_data="ybu:4부")],
        [InlineKeyboardButton("5부", callback_data="ybu:5부"),
         InlineKeyboardButton("6부", callback_data="ybu:6부"),
         InlineKeyboardButton("7부", callback_data="ybu:7부")],
        [InlineKeyboardButton("📚 대학부", callback_data="ybu:대학부"),
         InlineKeyboardButton("🌱 새신자부", callback_data="ybu:새신자부")],
        [InlineKeyboardButton("⚙️ 기능과", callback_data="ybu:기능과")],
    ])


def function_dept_keyboard():
    """기능과 10개 부서"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👑 회장단", callback_data="fdept:회장단"),
         InlineKeyboardButton("🏫 총교관", callback_data="fdept:총교관")],
        [InlineKeyboardButton("📋 기획문화과", callback_data="fdept:기획문화과"),
         InlineKeyboardButton("💬 상담심방과", callback_data="fdept:상담심방과")],
        [InlineKeyboardButton("📖 교육과", callback_data="fdept:교육과"),
         InlineKeyboardButton("⚽ 사업체육과", callback_data="fdept:사업체육과")],
        [InlineKeyboardButton("🤝 섭외과", callback_data="fdept:섭외과"),
         InlineKeyboardButton("🚗 봉사교통과", callback_data="fdept:봉사교통과")],
        [InlineKeyboardButton("✈️ 해외전도과", callback_data="fdept:해외전도과"),
         InlineKeyboardButton("📣 전도과", callback_data="fdept:전도과")],
    ])


def youth_7bu_gu_keyboard():
    """청년회 7부 구역 선택 (1~11구역, 국제부, 부장가편)"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1구역", callback_data="y7gu:1"),
         InlineKeyboardButton("2구역", callback_data="y7gu:2"),
         InlineKeyboardButton("3구역", callback_data="y7gu:3"),
         InlineKeyboardButton("4구역", callback_data="y7gu:4")],
        [InlineKeyboardButton("5구역", callback_data="y7gu:5"),
         InlineKeyboardButton("6구역", callback_data="y7gu:6"),
         InlineKeyboardButton("7구역", callback_data="y7gu:7"),
         InlineKeyboardButton("8구역", callback_data="y7gu:8")],
        [InlineKeyboardButton("9구역", callback_data="y7gu:9"),
         InlineKeyboardButton("10구역", callback_data="y7gu:10"),
         InlineKeyboardButton("11구역", callback_data="y7gu:11")],
        [InlineKeyboardButton("🌐 국제부 구역", callback_data="y7gu:국제부"),
         InlineKeyboardButton("📋 부장가편 구역", callback_data="y7gu:부장가편")],
    ])


def chairman_keyboard(group: str = ""):
    """회장단/새신자부 버튼 (부녀회/장년회/자문회용)
    부녀회만 3040부 버튼 추가"""
    rows = [
        [InlineKeyboardButton("👑 회장단", callback_data="chair:회장단"),
         InlineKeyboardButton("🌱 새신자부", callback_data="chair:새신자부")],
    ]
    if group == "부녀회":
        rows.append(
            [InlineKeyboardButton("✨ 3040부", callback_data="chair:3040")]
        )
    return InlineKeyboardMarkup(rows)


def webapp_button(user_id: int, text: str = "🚀 암기 훈련 시작하기"):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(text, url=f"{WEBAPP_URL}?uid={user_id}")
    ]])


# ─────────────── 헬퍼 ───────────────
def fetch_profile(user_id: int):
    """Firestore users/{telegram_id} 조회"""
    try:
        snap = db.collection("users").document(str(user_id)).get()
        if snap.exists:
            data = snap.to_dict() or {}
            try:
                db.collection("users").document(str(user_id)).update(
                    {"lastLogin": firestore.SERVER_TIMESTAMP}
                )
            except Exception:
                pass
            return data
    except Exception:
        logging.exception("프로필 조회 실패")
    return None


def format_team_label(profile: dict) -> str:
    """프로필 → 표시용 라벨"""
    group = profile.get("group", "")

    # 교역자: 부서 텍스트
    if group == "교역자":
        dept = profile.get("dept", "")
        return dept if dept else ""

    # 청년회
    if group == "청년회":
        bu = profile.get("bu")
        gu = profile.get("gu")
        dept = profile.get("dept", "")

        bu_str = ""
        if bu not in (None, "", 0):
            bu_str = str(bu)
            if bu_str.isdigit():
                bu_str = f"{bu_str}부"

        if bu_str == "기능과" and dept:
            return f"{bu_str} {dept}"

        parts = [bu_str] if bu_str else []
        if gu not in (None, "", 0):
            gu_str = str(gu)
            if gu_str.isdigit():
                gu_str = f"{gu_str}구역"
            elif gu_str in ("국제부", "부장가편"):
                gu_str = f"{gu_str} 구역"
            parts.append(gu_str)
        return " ".join(parts)

    # 부녀회/장년회/자문회
    bu = profile.get("bu")
    team = profile.get("team")
    gu = profile.get("gu")

    if str(bu) == "회장단":
        return "회장단"

    parts = []
    if bu not in (None, "", 0):
        bu_str = str(bu)
        if bu_str.isdigit():
            bu_str = f"{bu_str}부"
        elif bu_str == "3040":
            bu_str = "3040부"
        parts.append(bu_str)
    if team not in (None, "", 0):
        team_str = str(team)
        if team_str.isdigit():
            team_str = f"{team_str}팀"
        parts.append(team_str)
    if gu not in (None, "", 0):
        gu_str = str(gu)
        if gu_str.isdigit():
            gu_str = f"{gu_str}구역"
        parts.append(gu_str)
    return " ".join(parts)


def parse_number(text: str):
    cleaned = text.replace(" ", "").replace("부", "").replace("팀", "").replace("구역", "")
    try:
        n = int(cleaned)
        if n < 0 or n > 999:
            return None
        return n
    except ValueError:
        return None


# ─────────────── /start ───────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    context.user_data.clear()

    profile = fetch_profile(user.id)

    if profile:
        team_label = format_team_label(profile)
        sub = f"({profile.get('group', '')}"
        if team_label:
            sub += f" / {team_label}"
        sub += ")"

        await update.message.reply_text(
            f"{profile.get('name','')}님 안녕하세요! 👋\n"
            f"{sub}\n\n"
            f"📖 오늘도 말씀 암기 훈련 하러 가볼까요?\n"
            f"💡 구절 보기: /계1장 /계7장 /계10장 /계20장 /계22장\n"
            f"💡 내 점수: /score\n"
            f"💡 정보 변경: /register",
            reply_markup=webapp_button(user.id, "🚀 훈련 시작하기"),
        )
    else:
        context.user_data["stage"] = "reg_group"
        await update.message.reply_text(
            "안녕하세요! 요한계시록 암기 훈련 봇입니다 📖\n"
            "먼저 소속을 등록해주세요.",
            reply_markup=group_keyboard(),
        )


async def cmd_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["stage"] = "reg_group"
    await update.message.reply_text(
        "어디 소속이신가요?",
        reply_markup=group_keyboard(),
    )


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("취소되었습니다.")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *요한계시록 암기 훈련 봇*\n\n"
        "/계1장 — 계 1장 1~3절 보기\n"
        "/계7장 — 계 7장 1~4절 보기\n"
        "/계10장 — 계 10장 10~11절 보기\n"
        "/계20장 — 계 20장 4~6절 보기\n"
        "/계22장 — 계 22장 18~19절 보기\n"
        "/score — 내 진도 및 순위 확인\n"
        "/rank — 전체 순위 TOP 10\n"
        "/register — 소속 정보 변경\n"
        "/cancel — 진행 중인 작업 취소",
        parse_mode="Markdown",
    )


# ─────────────── 텍스트 입력 (등록 단계) ───────────────
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    stage = context.user_data.get("stage")

    # ── 등록: 이름 ──
    if stage == "reg_name":
        if len(text) > 20 or len(text) < 1:
            await update.message.reply_text("❗ 이름은 1~20자로 입력해주세요.")
            return
        context.user_data["reg_name"] = text

        group = context.user_data.get("reg_group")
        if group == "교역자":
            context.user_data["stage"] = "reg_dept"
            await update.message.reply_text(
                f"{text}님, 반가워요! 😊\n\n"
                f"어느 부서이신가요?\n"
                f"(예: 교육부, 청년부, 행정부)"
            )
        elif group == "청년회":
            context.user_data["stage"] = "reg_youth_bu"
            await update.message.reply_text(
                f"{text}님, 반가워요! 😊\n\n"
                f"어느 부이신가요?",
                reply_markup=youth_bu_keyboard(),
            )
        else:
            context.user_data["stage"] = "reg_bu"
            if group == "부녀회":
                extra_btn_text = "👑 회장단 / 🌱 새신자부 / ✨ 3040부는 아래 버튼!"
            else:
                extra_btn_text = "👑 회장단 / 🌱 새신자부는 아래 버튼!"

            await update.message.reply_text(
                f"{text}님, 반가워요! 😊\n\n"
                f"몇 부이신가요?\n"
                f"숫자만 입력 (예: 2)\n\n"
                f"{extra_btn_text}",
                reply_markup=chairman_keyboard(group),
            )
        return

    # ── 등록: 교역자 부서 ──
    if stage == "reg_dept":
        if len(text) > 20 or len(text) < 1:
            await update.message.reply_text("❗ 부서는 1~20자로 입력해주세요.")
            return
        context.user_data["reg_dept"] = text
        await save_profile(update, context)
        return

    # ── 등록: 부 (부녀회/장년회/자문회) ──
    if stage == "reg_bu":
        bu = parse_number(text)
        if bu is None:
            group = context.user_data.get("reg_group", "")
            extra = "💡 3040부는 아래 ✨3040부 버튼\n" if group == "부녀회" else ""
            await update.message.reply_text(
                "❗ 숫자만 입력해주세요. (예: 2)\n"
                f"{extra}"
                "💡 회장단/새신자부는 아래 버튼"
            )
            return
        context.user_data["reg_bu"] = bu
        context.user_data["stage"] = "reg_team"
        await update.message.reply_text(
            f"{bu}부 ✅\n\n몇 팀이신가요?\n(숫자만 입력. 예: 3)"
        )
        return

    # ── 등록: 팀 ──
    if stage == "reg_team":
        team = parse_number(text)
        if team is None:
            await update.message.reply_text("❗ 숫자만 입력해주세요. (예: 3)")
            return
        context.user_data["reg_team"] = team
        context.user_data["stage"] = "reg_gu"
        await update.message.reply_text(
            f"{team}팀 ✅\n\n몇 구역이신가요?\n(숫자만 입력. 예: 5)"
        )
        return

    # ── 등록: 구역 → 저장 ──
    if stage == "reg_gu":
        gu = parse_number(text)
        if gu is None:
            await update.message.reply_text("❗ 숫자만 입력해주세요. (예: 5)")
            return
        context.user_data["reg_gu"] = gu
        await save_profile(update, context)
        return

    # ── 일반 ──
    if not stage:
        await update.message.reply_text(
            "👋 /start 를 눌러 시작해주세요!\n도움말: /help"
        )
        return


# ─────────────── 프로필 저장 ───────────────
async def save_profile(update_or_query, context: ContextTypes.DEFAULT_TYPE):
    """update 또는 callback_query 둘 다 받을 수 있게"""
    if hasattr(update_or_query, 'from_user') and not hasattr(update_or_query, 'effective_message'):
        user = update_or_query.from_user
        message = update_or_query.message
    else:
        user = update_or_query.message.from_user
        message = update_or_query.message

    group = context.user_data.get("reg_group", "")
    name = context.user_data.get("reg_name", "")
    bu = context.user_data.get("reg_bu", "")
    team = context.user_data.get("reg_team", "")
    gu = context.user_data.get("reg_gu", "")
    dept = context.user_data.get("reg_dept", "")

    processing = await message.reply_text("⏳ 등록 중이에요...")

    try:
        uid_str = str(user.id)
        doc_ref = db.collection("users").document(uid_str)
        existing = doc_ref.get()

        data = {
            "uid": uid_str,
            "name": name,
            "group": group,
            "bu": bu if bu != "" else "",
            "team": team if team != "" else "",
            "gu": gu if gu != "" else "",
            "dept": dept if dept != "" else "",
            "telegramId": user.id,
            "lastLogin": firestore.SERVER_TIMESTAMP,
        }
        if not existing.exists:
            data["joinedAt"] = firestore.SERVER_TIMESTAMP

        doc_ref.set(data, merge=True)

        profile = {
            "group": group, "name": name,
            "bu": bu, "team": team, "gu": gu, "dept": dept,
        }
        context.user_data.clear()

        team_label = format_team_label(profile)
        sub = group
        if team_label:
            sub += f" {team_label}"

        try:
            await processing.delete()
        except Exception:
            pass

        await message.reply_text(
            f"✅ 등록 완료!\n\n"
            f"이름: {name}\n"
            f"소속: {sub}\n\n"
            f"아래 링크에서 암기 훈련을 시작하세요 🎉",
            reply_markup=webapp_button(user.id, "🚀 암기 훈련 시작하기"),
        )
    except Exception:
        logging.exception("프로필 저장 실패")
        try:
            await processing.delete()
        except Exception:
            pass
        await message.reply_text("❌ 등록 실패. 다시 시도해주세요.\n/register")
        context.user_data.clear()


# ─────────────── 콜백 (등록 버튼) ───────────────
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = query.data

    # 소속 선택
    if action.startswith("grp:"):
        group = action.split(":", 1)[1]
        context.user_data["reg_group"] = group
        context.user_data["stage"] = "reg_name"
        await query.message.reply_text(
            f"✅ {group} 선택!\n\n"
            f"이름을 알려주세요. 😊\n"
            f"(예: 김강동)"
        )
        return

    # 청년회 부 선택
    if action.startswith("ybu:"):
        bu = action.split(":", 1)[1]
        context.user_data["reg_bu"] = bu

        if bu == "기능과":
            context.user_data["stage"] = "reg_youth_fdept"
            await query.message.reply_text(
                f"⚙️ 기능과 ✅\n\n"
                f"어느 과이신가요?",
                reply_markup=function_dept_keyboard(),
            )
        elif bu == "7부":
            context.user_data["stage"] = "reg_youth_7gu"
            await query.message.reply_text(
                f"7부 ✅\n\n"
                f"어느 구역이신가요?",
                reply_markup=youth_7bu_gu_keyboard(),
            )
        else:
            context.user_data["stage"] = "reg_gu"
            await query.message.reply_text(
                f"{bu} ✅\n\n"
                f"몇 구역이신가요?\n"
                f"(숫자만 입력. 예: 5)"
            )
        return

    # 청년회 7부 구역 선택 → 바로 저장
    if action.startswith("y7gu:"):
        gu = action.split(":", 1)[1]
        if gu.isdigit():
            context.user_data["reg_gu"] = int(gu)
        else:
            context.user_data["reg_gu"] = gu
        await save_profile(query, context)
        return

    # 청년회 기능과 부서 선택 → 바로 저장
    if action.startswith("fdept:"):
        dept = action.split(":", 1)[1]
        context.user_data["reg_dept"] = dept
        context.user_data["reg_gu"] = ""
        await save_profile(query, context)
        return

    # 회장단/새신자부/3040부 버튼
    if action.startswith("chair:"):
        choice = action.split(":", 1)[1]

        if choice == "회장단":
            context.user_data["reg_bu"] = "회장단"
            context.user_data["reg_team"] = ""
            context.user_data["reg_gu"] = ""
            await save_profile(query, context)
            return

        elif choice == "새신자부":
            context.user_data["reg_bu"] = "새신자부"
            context.user_data["reg_team"] = ""
            context.user_data["stage"] = "reg_gu"
            await query.message.reply_text(
                f"🌱 새신자부 ✅\n\n"
                f"몇 구역이신가요?\n"
                f"(숫자만 입력. 예: 5)"
            )
            return

        elif choice == "3040":
            context.user_data["reg_bu"] = "3040"
            context.user_data["reg_team"] = ""
            context.user_data["stage"] = "reg_gu"
            await query.message.reply_text(
                f"✨ 3040부 ✅\n\n"
                f"몇 구역이신가요?\n"
                f"(숫자만 입력. 예: 5)"
            )
            return


# ─────────────── 구절 보기 ───────────────
VERSE_TEXTS = {
    "rev1": (
        "*📖 계 1장 1~3절*\n\n"
        "1절 예수 그리스도의 계시라 이는 하나님이 그에게 주사 반드시 속히 될 일을 그 종들에게 보이시려고 그 천사를 그 종 요한에게 보내어 지시하신 것이라\n"
        "2절 요한은 하나님의 말씀과 예수 그리스도의 증거 곧 자기의 본 것을 다 증거하였느니라\n"
        "3절 이 예언의 말씀을 읽는 자와 듣는 자들과 그 가운데 기록한 것을 지키는 자들이 복이 있나니 때가 가까움이라"
    ),
    "rev7": (
        "*📖 계 7장 1~4절*\n\n"
        "1절 이 일 후에 내가 네 천사가 땅 네 모퉁이에 선 것을 보니 땅의 사방의 바람을 붙잡아 바람으로 하여금 땅에나 바다에나 각종 나무에 불지 못하게 하더라\n"
        "2절 또 보매 다른 천사가 살아 계신 하나님의 인을 가지고 해 돋는 데로부터 올라와서 땅과 바다를 해롭게 할 권세를 얻은 네 천사를 향하여 큰 소리로 외쳐\n"
        "3절 가로되 우리가 우리 하나님의 종들의 이마에 인치기까지 땅이나 바다나 나무나 해하지 말라 하더라\n"
        "4절 내가 인 맞은 자의 수를 들으니 이스라엘 자손의 각 지파 중에서 인 맞은 자들이 십사만 사천이니"
    ),
    "rev10": (
        "*📖 계 10장 10~11절*\n\n"
        "10절 내가 천사의 손에서 작은 책을 갖다 먹어버리니 내 입에는 꿀같이 다나 먹은 후에 내 배에서는 쓰게 되더라\n"
        "11절 저가 내게 말하기를 네가 많은 백성과 나라와 방언과 임금에게 다시 예언하여야 하리라 하더라"
    ),
    "rev20": (
        "*📖 계 20장 4~6절*\n\n"
        "4절 또 내가 보좌들을 보니 거기 앉은 자들이 있어 심판하는 권세를 받았더라 또 내가 보니 예수의 증거와 하나님의 말씀을 인하여 목 베임을 받은 자의 영혼들과 또 짐승과 그의 우상에게 경배하지도 아니하고 이마와 손에 그의 표를 받지도 아니한 자들이 살아서 그리스도로 더불어 천 년 동안 왕 노릇 하니\n"
        "5절 (그 나머지 죽은 자들은 그 천 년이 차기까지 살지 못하더라) 이는 첫째 부활이라\n"
        "6절 이 첫째 부활에 참예하는 자들은 복이 있고 거룩하도다 둘째 사망이 그들을 다스리는 권세가 없고 도리어 그들이 하나님과 그리스도의 제사장이 되어 천 년 동안 그리스도로 더불어 왕 노릇 하리라"
    ),
    "rev22": (
        "*📖 계 22장 18~19절*\n\n"
        "18절 내가 이 책의 예언의 말씀을 듣는 각인에게 증거하노니 만일 누구든지 이것들 외에 더하면 하나님이 이 책에 기록된 재앙들을 그에게 더하실 터이요\n"
        "19절 만일 누구든지 이 책의 예언의 말씀에서 제하여 버리면 하나님이 이 책에 기록된 생명나무와 및 거룩한 성에 참예함을 제하여 버리시리라"
    ),
}

VERSE_LABELS = {
    "rev1": "계 1장",
    "rev7": "계 7장",
    "rev10": "계 10장",
    "rev20": "계 20장",
    "rev22": "계 22장",
}


async def send_verse(update: Update, verse_id: str):
    user = update.message.from_user
    text = VERSE_TEXTS[verse_id]
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=webapp_button(user.id, "🚀 암기 훈련 하러가기"),
    )


async def cmd_rev1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_verse(update, "rev1")


async def cmd_rev7(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_verse(update, "rev7")


async def cmd_rev10(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_verse(update, "rev10")


async def cmd_rev20(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_verse(update, "rev20")


async def cmd_rev22(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_verse(update, "rev22")


# ─────────────── /점수 ───────────────
def progress_bar(completed: int) -> str:
    """완료된 단계 수(0~5) → 진도 바 + 라벨"""
    bars = {
        0: ("░░░░░░░░", "미시작"),
        1: ("██░░░░░░", "1/5단계"),
        2: ("████░░░░", "2/5단계"),
        3: ("██████░░", "3/5단계"),
        4: ("███████░", "4/5단계"),
        5: ("████████", "5/5단계 완료✅"),
    }
    bar, label = bars.get(max(0, min(5, completed)), bars[0])
    return f"{bar} {label}"


def get_completed_stage(score_doc: dict) -> int:
    """scores 문서에서 완료된 최고 단계 (0~5) 반환"""
    if not score_doc:
        return 0
    if score_doc.get("mastered") or score_doc.get("stage5done"):
        return 5
    for n in (5, 4, 3, 2, 1):
        if score_doc.get(f"stage{n}done"):
            return n
    return 0


async def cmd_score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    profile = fetch_profile(user.id)

    if not profile:
        await update.message.reply_text(
            "📝 먼저 등록이 필요해요!\n/start 를 눌러주세요."
        )
        return

    # 점수 문서 조회: scores/{uid} 안에 {rev1:{...}, rev7:{...}, ...} 구조
    score_docs = {}
    try:
        snap = db.collection("scores").document(str(user.id)).get()
        if snap.exists:
            score_docs = snap.to_dict() or {}
    except Exception:
        logging.exception("점수 조회 실패")

    team_label = format_team_label(profile)
    sub = profile.get("group", "")
    if team_label:
        sub += f" {team_label}"

    lines = []
    for vid, label in VERSE_LABELS.items():
        completed = get_completed_stage(score_docs.get(vid) if isinstance(score_docs.get(vid), dict) else None)
        lines.append(f"{label}  {progress_bar(completed)}")

    # 전체 순위 계산
    my_rank_str = ""
    try:
        my_mastered = sum(1 for vid in VERSE_LABELS if (score_docs.get(vid) or {}).get("mastered"))
        lb_snap = db.collection("leaderboard").get()
        higher = 0
        for d in lb_snap:
            dd = d.to_dict() or {}
            if (dd.get("totalMastered", 0) or 0) > my_mastered:
                higher += 1
        my_rank_str = f"\n\n전체 순위: {higher + 1}위"
    except Exception:
        logging.exception("순위 계산 실패")

    msg = (
        f"📊 *{profile.get('name','')}님의 현황*\n"
        f"소속: {sub}\n\n"
        f"```\n"
        + "\n".join(lines)
        + f"\n```"
        + my_rank_str
    )

    await update.message.reply_text(
        msg,
        parse_mode="Markdown",
        reply_markup=webapp_button(user.id, "🚀 훈련 계속하기"),
    )


# ─────────────── /순위 ───────────────
async def cmd_rank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user

    try:
        lb_snap = list(db.collection("leaderboard").get())
        items = []
        for d in lb_snap:
            dd = d.to_dict() or {}
            items.append({
                "id": d.id,
                "name": dd.get("name", "?"),
                "group": dd.get("group", ""),
                "totalMastered": dd.get("totalMastered", 0) or 0,
                "accuracy": dd.get("accuracy", 0) or 0,
            })
        # totalMastered desc, accuracy desc
        items.sort(key=lambda x: (-x["totalMastered"], -x["accuracy"]))
    except Exception:
        logging.exception("순위 조회 실패")
        await update.message.reply_text("❌ 순위를 불러올 수 없어요.")
        return

    if not items:
        await update.message.reply_text("🏆 *전체 순위 TOP 10*\n\n아직 기록이 없습니다.",
                                        parse_mode="Markdown")
        return

    medals = ["🥇", "🥈", "🥉"]
    lines = ["🏆 *전체 순위 TOP 10*\n"]
    for i, it in enumerate(items[:10], 1):
        medal = medals[i - 1] if i <= 3 else f"{i}."
        group_str = it["group"] or ""
        tm = it["totalMastered"]
        mark = " ✅" if tm >= 5 else ""
        sub = f" ({group_str})" if group_str else ""
        lines.append(f"{medal} {it['name']}{sub} — {tm}구절{mark}")

    # 내 순위 (leaderboard 안에 있을 때만)
    my_rank = None
    for idx, it in enumerate(items, 1):
        if it["id"] == str(user.id):
            my_rank = idx
            break

    if my_rank is not None:
        lines.append(f"\n내 순위: {my_rank}위")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ─────────────── 더미 서버 ───────────────
class HealthHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        html = """<!DOCTYPE html><html><head><meta charset='utf-8'>
<title>요한계시록 암기 훈련 봇</title></head>
<body style='font-family:sans-serif;text-align:center;padding:50px;'>
<h1>📖 요한계시록 암기 훈련</h1>
<p>봇이 정상 작동 중입니다 ✅</p>
</body></html>"""
        self.wfile.write(html.encode("utf-8"))

    def log_message(self, format, *args):
        return


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def start_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    try:
        with ReusableTCPServer(("0.0.0.0", port), HealthHandler) as httpd:
            print(f"더미 웹서버 실행 중 (포트 {port})")
            httpd.serve_forever()
    except Exception as e:
        logging.exception(f"더미 서버 에러: {e}")


# ─────────────── 좀비 봇 정리 ───────────────
def cleanup_telegram():
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/deleteWebhook?drop_pending_updates=true"
        res = requests.get(url, timeout=10)
        logging.info(f"좀비 폴링 정리: {res.json()}")
    except Exception as e:
        logging.warning(f"좀비 정리 실패 (무시하고 계속): {e}")


# ─────────────── 메인 ───────────────
def main():
    port = int(os.environ.get("PORT", 10000))
    print(f"포트 {port}에서 시작합니다")

    cleanup_telegram()
    threading.Thread(target=start_dummy_server, daemon=True).start()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("register", cmd_register))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("score", cmd_score))
    app.add_handler(CommandHandler("rank", cmd_rank))
    app.add_handler(CommandHandler("계1장", cmd_rev1))
    app.add_handler(CommandHandler("계7장", cmd_rev7))
    app.add_handler(CommandHandler("계10장", cmd_rev10))
    app.add_handler(CommandHandler("계20장", cmd_rev20))
    app.add_handler(CommandHandler("계22장", cmd_rev22))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_callback))

    print("봇 실행 중...")

    while True:
        try:
            app.run_polling(drop_pending_updates=True, close_loop=False)
            break
        except Exception as e:
            logging.exception(f"봇 폴링 에러: {e}")
            err_str = str(e).lower()
            if "conflict" in err_str:
                logging.warning("⚠️ Conflict 감지, 좀비 정리 후 재시작...")
                time.sleep(5)
                cleanup_telegram()
                time.sleep(3)
                continue
            else:
                raise


if __name__ == "__main__":
    main()
