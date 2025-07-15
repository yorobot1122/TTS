import discord
from discord.ext import commands
import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 경고 데이터 저장 파일
WARN_FILE = "warns.json"

# 봇 설정
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# 운영진 역할 ID
ADMIN_ROLE_ID = 1394354535555923988

# 경고 데이터 로드 함수
def load_warns():
    if os.path.exists(WARN_FILE):
        with open(WARN_FILE, 'r') as f:
            return json.load(f)
    return {}

# 경고 데이터 저장 함수
def save_warns(data):
    with open(WARN_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# 운영진 권한 체크 데코레이터
def is_guild_admin():
    async def predicate(ctx):
        role = discord.utils.get(ctx.guild.roles, id=ADMIN_ROLE_ID)
        if role not in ctx.author.roles:
            await ctx.send("⚠️ 이 명령어는 운영진만 사용 가능합니다.")
            return False
        return True
    return commands.check(predicate)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    await bot.change_presence(activity=discord.Game(name="!도움말"))

############################################
#              명령어 구현 영역              #
############################################

# 1. 길드원 추방
@bot.command(name="추방")
@is_guild_admin()
async def kick_member(ctx, member: discord.Member, *, reason="사유 없음"):
    await member.kick(reason=f"운영자: {ctx.author} - {reason}")
    await ctx.send(f"✅ **{member.display_name}** 님을 추방했습니다. (사유: {reason})")

# 2. 길드원 차단 (영구 추방 + 재입장 차단)
@bot.command(name="차단")
@is_guild_admin()
async def ban_member(ctx, member: discord.Member, *, reason="사유 없음"):
    await member.ban(reason=f"운영자: {ctx.author} - {reason}", delete_message_days=0)
    await ctx.send(f"⛔ **{member.display_name}** 님을 영구 차단했습니다. (사유: {reason})")

# 3. 타임아웃 (일정 시간 동안 채팅 금지)
@bot.command(name="타임아웃")
@is_guild_admin()
async def timeout_member(ctx, member: discord.Member, minutes: int, *, reason="사유 없음"):
    # 시간 제한 (최대 7일)
    duration = min(minutes, 60 * 24 * 7)  # 7일 이내로 제한
    until = datetime.utcnow() + timedelta(minutes=duration)
    
    await member.timeout(until, reason=f"운영자: {ctx.author} - {reason}")
    await ctx.send(f"⏳ **{member.display_name}** 님을 {duration}분간 타임아웃했습니다. (사유: {reason})")

# 4. 타임아웃 해제
@bot.command(name="타임아웃해제")
@is_guild_admin()
async def remove_timeout(ctx, member: discord.Member):
    await member.timeout(None)
    await ctx.send(f"🔓 **{member.display_name}** 님의 타임아웃을 해제했습니다.")

# 5. 경고 부여
@bot.command(name="경고")
@is_guild_admin()
async def warn_member(ctx, member: discord.Member, *, reason):
    warns_data = load_warns()
    guild_id = str(ctx.guild.id)
    user_id = str(member.id)
    
    if guild_id not in warns_data:
        warns_data[guild_id] = {}
    if user_id not in warns_data[guild_id]:
        warns_data[guild_id][user_id] = {"count": 0, "reasons": []}
    
    warns_data[guild_id][user_id]["count"] += 1
    warns_data[guild_id][user_id]["reasons"].append(reason)
    save_warns(warns_data)
    
    await ctx.send(f"⚠️ **{member.display_name}** 님에게 경고를 부여했습니다. (총 {warns_data[guild_id][user_id]['count']}회)")

# 6. 경고 조회
@bot.command(name="경고조회")
@is_guild_admin()
async def check_warns(ctx, member: discord.Member):
    warns_data = load_warns()
    guild_id = str(ctx.guild.id)
    user_id = str(member.id)
    
    if guild_id in warns_data and user_id in warns_data[guild_id]:
        warn_info = warns_data[guild_id][user_id]
        embed = discord.Embed(
            title=f"{member.display_name}님의 경고 기록",
            description=f"총 {warn_info['count']}회 경고",
            color=0xff9900
        )
        for i, reason in enumerate(warn_info["reasons"], 1):
            embed.add_field(name=f"경고 {i}회", value=reason, inline=False)
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"ℹ️ **{member.display_name}** 님의 경고 기록이 없습니다.")

# 7. 경고 초기화
@bot.command(name="경고초기화")
@is_guild_admin()
async def clear_warns(ctx, member: discord.Member):
    warns_data = load_warns()
    guild_id = str(ctx.guild.id)
    user_id = str(member.id)
    
    if guild_id in warns_data and user_id in warns_data[guild_id]:
        del warns_data[guild_id][user_id]
        save_warns(warns_data)
        await ctx.send(f"🔄 **{member.display_name}** 님의 경고 기록을 초기화했습니다.")
    else:
        await ctx.send(f"ℹ️ **{member.display_name}** 님의 경고 기록이 없습니다.")

# 8. 도움말
@bot.command(name="도움말")
async def help_command(ctx):
    embed = discord.Embed(
        title="📜 운영진 명령어 도움말",
        description="아래 명령어들은 운영진 역할만 사용 가능합니다",
        color=0x7289da
    )
    
    commands = [
        ("!추방 [@유저] [사유]", "서버에서 유저 추방"),
        ("!차단 [@유저] [사유]", "유저 영구 차단 (재입장 불가)"),
        ("!타임아웃 [@유저] [분] [사유]", "유저 채팅 금지 (최대 7일)"),
        ("!타임아웃해제 [@유저]", "타임아웃 해제"),
        ("!경고 [@유저] [사유]", "경고 부여"),
        ("!경고조회 [@유저]", "경고 기록 조회"),
        ("!경고초기화 [@유저]", "경고 기록 초기화"),
        ("!정보 [@유저]", "유저 정보 조회"),
        ("!서버상태", "서버 상태 확인")
    ]
    
    for name, value in commands:
        embed.add_field(name=name, value=value, inline=False)
    
    embed.set_footer(text=f"운영진 역할 ID: {ADMIN_ROLE_ID}")
    await ctx.send(embed=embed)

############################################
#                 봇 실행                  #
############################################
bot.run(os.getenv("DISCORD_BOT_TOKEN"))  # .env에서 토큰 로드
