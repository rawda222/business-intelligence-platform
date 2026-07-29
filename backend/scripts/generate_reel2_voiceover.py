from __future__ import annotations

import subprocess
from pathlib import Path

from google.api_core.client_options import ClientOptions
from google.cloud import texttospeech


BACKEND_DIR = Path(__file__).resolve().parents[1]

AUDIO_DIR = (
    BACKEND_DIR
    / "assets"
    / "najdi_campaign"
    / "20_audio"
)

WORK_DIR = (
    BACKEND_DIR
    / "generated"
    / "najdi_voiceover_work"
)

AUDIO_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

WORK_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


MODEL_NAME = (
    "gemini-3.1-flash-tts-preview"
)

LANGUAGE_CODE = "ar-001"

VOICE_NAME = "Charon"


RAW_VOICE_PATH = (
    WORK_DIR
    / "reel2_voiceover_raw.wav"
)

FINAL_VOICE_PATH = (
    AUDIO_DIR
    / "reel2_voiceover.wav"
)


SCRIPT = """
ودّك بطعم يفتح النفس؟

في مطعم شعبي نجدي، كل طبق له حكاية.

رز مضبوط، ولحم وفراخ على أصولها.

ومشويات بنكهة تخليك ترجع لها مرّة ثانية.

اختيارات تناسب كل السفرة،
وطعم نجدي يجمعكم.

اطلبه الحين من مطعم شعبي نجدي،
عبر جاهز، هنقرستيشن، أو نينجا.
""".strip()

STYLE_PROMPT = """
أدِّ النص كتعليق صوتي لإعلان قصير لمطعم سعودي على تيك توك.

اللهجة:
استخدم لهجة سعودية نجدية خفيفة وطبيعية، كما تُسمع في
الإعلانات التجارية الحديثة في مدينة الرياض.
يجب ألا يكون النطق مصريًا أو شاميًا أو بأسلوب مذيع أخبار رسمي.

الصوت:
استخدم صوتًا واضحًا ودافئًا وواثقًا وقريبًا من المستمع.
اجعل الأداء مناسبًا لإعلان مطعم شعبي نجدي يعرض تنوع الأطباق.

الأداء:
ابدأ بجملة جذابة تشد الانتباه من أول ثانية، دون صراخ.
استخدم ابتسامة صوتية خفيفة وطاقة إعلانية طبيعية.
اجعل السرعة متوسطة مائلة للسرعة.
استخدم وقفات قصيرة وواضحة بين الجمل.
اجعل مدة القراءة قريبة من ثمانٍ وعشرين ثانية.
اترك وقفة قصيرة قبل جملة الطلب الأخيرة.

النطق:
انطق عبارة مطعم شعبي نجدي بنطق سعودي طبيعي.
انطق كلمة رز بالنطق السعودي الطبيعي.
انطق أسماء تطبيقات الطلب بوضوح:
جاهز، هنقرستيشن، نينجا.

اقرأ النص المكتوب فقط.
لا تضف أي كلمات أو مقدمة أو خاتمة.
لا تضف موسيقى أو مؤثرات صوتية.
قدّم التعليق الصوتي فقط.
""".strip()
def run(
    command: list[str],
) -> None:
    print()
    print(
        "$",
        subprocess.list2cmdline(
            command
        ),
    )

    subprocess.run(
        command,
        check=True,
    )


def create_client(
) -> texttospeech.TextToSpeechClient:
    return texttospeech.TextToSpeechClient(
        client_options=ClientOptions(
            api_endpoint=(
                "texttospeech.googleapis.com"
            )
        )
    )


def generate_saudi_voiceover() -> None:
    client = create_client()

    synthesis_input = (
        texttospeech.SynthesisInput(
            text=SCRIPT,
            prompt=STYLE_PROMPT,
        )
    )

    voice = (
        texttospeech.VoiceSelectionParams(
            language_code=LANGUAGE_CODE,
            name=VOICE_NAME,
            model_name=MODEL_NAME,
        )
    )

    audio_config = (
        texttospeech.AudioConfig(
            audio_encoding=(
                texttospeech
                .AudioEncoding
                .LINEAR16
            ),
            sample_rate_hertz=24000,
        )
    )

    print(
        "Generating Saudi Najdi voiceover..."
    )

    print(
        f"Model: {MODEL_NAME}"
    )

    print(
        f"Voice: {VOICE_NAME}"
    )

    print(
        f"Language: {LANGUAGE_CODE}"
    )

    response = client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config,
    )

    if not response.audio_content:
        raise RuntimeError(
            "Cloud TTS returned empty audio."
        )

    RAW_VOICE_PATH.write_bytes(
        response.audio_content
    )

    print(
        "Raw voice created:",
        RAW_VOICE_PATH,
    )


def prepare_final_voiceover() -> None:
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(RAW_VOICE_PATH),
            "-af",
            (
                "highpass=f=80,"
                "lowpass=f=11500,"
                "acompressor="
                "threshold=0.12:"
                "ratio=2.0:"
                "attack=15:"
                "release=180,"
                "volume=1.05,"
                "alimiter=limit=0.92,"
                "loudnorm="
                "I=-16:"
                "LRA=7:"
                "TP=-1.5"
            ),
            "-ar",
            "48000",
            "-ac",
            "2",
            "-c:a",
            "pcm_s16le",
            str(FINAL_VOICE_PATH),
        ]
    )

    print()
    print(
        "Final Saudi voiceover:",
        FINAL_VOICE_PATH,
    )


def main() -> None:
    generate_saudi_voiceover()
    prepare_final_voiceover()


if __name__ == "__main__":
    main()