# bot.py
import os
import discord
from discord.ext import commands, tasks
from google.cloud import texttospeech
from dotenv import load_dotenv
import asyncio
import time

# 환경 변수 로드
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GOOGLE_APPLICATION_CREDENTIALS = "service-account-key.json"

# TTS 클라이언트 초기화
tts_client = texttospeech.TextToSpeechClient.from_service_account_file(
    GOOGLE_APPLICATION_CREDENTIALS
)

# Discord 봇 설정
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# 전역 변수 설정
current_voice = "ko-KR-Wavenet-A"  # 기본 음성
monitoring_channel_id = 1392110732929138758  # 모니터링할 텍스트 채널 ID
tts_channel_id = 1391778128069656589  # TTS 재생 음성 채널 ID
message_queue = asyncio.Queue()  # TTS 재생 대기열
is_playing = False  # 현재 재생 중인지 여부

def synthesize_speech(text, output_file="output.mp3"):
    """Google TTS를 사용하여 음성 합성"""
    synthesis_input = texttospeech.SynthesisInput(text=text)
    
    voice = texttospeech.VoiceSelectionParams(
        language_code="ko-KR",
        name=current_voice,
        ssml_gender=texttospeech.SsmlVoiceGender.MALE
    )
    
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )
    
    response = tts_client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config
    )
    
    with open(output_file, "wb") as out:
        out.write(response.audio_content)
    
    return output_file

@bot.event
async def on_ready():
    print(f'{bot.user.name}이(가) 성공적으로 로그인했습니다!')
    # 백그라운드 작업 시작
    cleanup_messages.start()
    tts_player.start()

@bot.event
async def on_message(message):
    # 특정 채널의 메시지를 큐에 추가 (봇 메시지 제외)
    if message.channel.id == monitoring_channel_id and not message.author.bot:
        # 명령어가 아닌 일반 메시지만 처리
        if not message.content.startswith('!'):
            await message_queue.put(message.content)
    
    # 명령어 처리
    await bot.process_commands(message)

@tasks.loop(minutes=30)
async def cleanup_messages():
    """30분마다 채팅 채널 메시지 삭제 (고정 메시지 제외)"""
    try:
        channel = bot.get_channel(monitoring_channel_id)
        if not channel:
            return
            
        # 30분 이상 지난 메시지 삭제
        async for message in channel.history(limit=100):
            if not message.pinned and (time.time() - message.created_at.timestamp()) > 1800:
                await message.delete()
    except Exception as e:
        print(f"메시지 삭제 오류: {e}")

@tasks.loop(seconds=1)
async def tts_player():
    """큐에 있는 메시지를 순차적으로 재생"""
    global is_playing
    
    if is_playing or message_queue.empty():
        return
    
    is_playing = True
    text = await message_queue.get()
    
    try:
        # 음성 채널 연결
        voice_channel = bot.get_channel(tts_channel_id)
        if not voice_channel:
            print("음성 채널을 찾을 수 없습니다.")
            return
            
        voice_client = discord.utils.get(bot.voice_clients, guild=voice_channel.guild)
        
        if not voice_client:
            voice_client = await voice_channel.connect()
        elif voice_client.channel.id != tts_channel_id:
            await voice_client.move_to(voice_channel)
        
        # TTS 생성 및 재생
        output_file = synthesize_speech(text, f"tts_{int(time.time())}.mp3")
        source = discord.FFmpegPCMAudio(output_file)
        
        def after_playing(e):
            global is_playing
            is_playing = False
            # 재생 후 파일 삭제
            if os.path.exists(output_file):
                os.remove(output_file)
        
        voice_client.play(source, after=after_playing)
        print(f"TTS 재생: {text}")
        
    except Exception as e:
        print(f"TTS 재생 오류: {e}")
        is_playing = False

@bot.command(name='voice')
@commands.has_permissions(administrator=True)
async def set_voice(ctx, voice_name: str):
    """TTS 음성 변경 (관리자 전용)"""
    global current_voice
    
    # 허용된 음성 목록
    allowed_voices = [
        "ko-KR-Wavenet-A", "ko-KR-Wavenet-B", "ko-KR-Wavenet-C", "ko-KR-Wavenet-D",
        "ko-KR-Standard-A", "ko-KR-Standard-B", "ko-KR-Standard-C", "ko-KR-Standard-D"
    ]
    
    if voice_name in allowed_voices:
        current_voice = voice_name
        await ctx.send(f"✅ 음성이 변경되었습니다: `{voice_name}`")
    else:
        await ctx.send(f"❌ 허용되지 않은 음성입니다. 다음 중 하나를 선택해주세요:\n{', '.join(allowed_voices)}")

# !tts 대신 ! 명령어로 변경 (모든 사용자 사용 가능)
@bot.command(name='!')
async def tts_shortcut(ctx, *, text: str):
    """텍스트를 음성으로 변환하여 재생 (모든 사용자 사용 가능)"""
    # 음성 채널 확인
    if not ctx.author.voice:
        await ctx.send("먼저 음성 채널에 접속해주세요!")
        return
    
    voice_channel = ctx.author.voice.channel
    
    # 봇이 음성 채널에 없으면 접속
    if not ctx.voice_client:
        await voice_channel.connect()
    elif ctx.voice_client.channel != voice_channel:
        await ctx.voice_client.move_to(voice_channel)
    
    # TTS 생성
    try:
        await ctx.send(f"🔊 '{text}' 변환 중...")
        output_file = synthesize_speech(text, f"tts_{ctx.message.id}.mp3")
        
        # 음성 재생
        source = discord.FFmpegPCMAudio(output_file)
        ctx.voice_client.play(
            source, 
            after=lambda e: os.remove(output_file) if os.path.exists(output_file) else None
        )
        
        await ctx.send(f"🎤 TTS 재생 중: **{text}**")
        
    except Exception as e:
        await ctx.send(f"❌ 오류 발생: {str(e)}")
        if os.path.exists(output_file):
            os.remove(output_file)

@bot.command(name='나가')
async def leave_command(ctx):
    """음성 채널에서 나가기"""
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("👋 음성 채널에서 나갔습니다.")
    else:
        await ctx.send("❌ 음성 채널에 연결되어 있지 않습니다.")

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
