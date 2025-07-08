# bot.py
import os
import discord
from discord.ext import commands
from google.cloud import texttospeech
from dotenv import load_dotenv

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

def synthesize_speech(text, output_file="output.mp3"):
    """Google TTS를 사용하여 음성 합성"""
    synthesis_input = texttospeech.SynthesisInput(text=text)
    
    voice = texttospeech.VoiceSelectionParams(
        language_code="ko-KR",
        name="ko-KR-Wavenet-A",  # 한국어 남성 음성
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

@bot.command(name='tts')
async def tts_command(ctx, *, text: str):
    """텍스트를 음성으로 변환하여 재생"""
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
