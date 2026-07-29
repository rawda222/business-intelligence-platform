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
    / "saudi_voiceover_raw.wav"
)

FINAL_VOICE_PATH = (
    AUDIO_DIR
    / "voiceover.wav"
)


SCRIPT = """
مطعم شعبي نجدي.

اللحم المخصوص، بتسعة وثلاثين ريال.

لحم طري، ورز مضبوط على أصوله.

طعم نجدي أصيل، يفتح النفس من أول لقمة.

سفرة تجمعكم على طعم يستاهل.

اطلبه الحين عبر جاهز، هنقرستيشن، أو نينجا.
""".strip()


STYLE_PROMPT = """
أدِّ النص كتعليق صوتي إعلاني قصير لمطعم في مدينة الرياض.

اللهجة:
لهجة سعودية نجدية خفيفة وطبيعية، كما تُسمع في الإعلانات
التجارية الحديثة في الرياض. يجب ألّا يكون النطق مصريًا أو
شاميًا أو بأسلوب مذيع أخبار بالفصحى.

الصوت:
صوت إعلاني سعودي واضح، دافئ، واثق، وقريب من المستمع.
يجب أن يبدو مناسبًا لإعلان مطعم نجدي فاخر على تيك توك.

الأداء:
ابدأ بطاقة واضحة تشد الانتباه من أول كلمة، ولكن بدون صراخ.
استخدم ابتسامة صوتية خفيفة ونبرة شهية ومحفزة.
اجعل السرعة متوسطة مائلة للسرعة.
استخدم وقفات قصيرة وطبيعية بين الجمل.
أبرز اسم مطعم شعبي نجدي، وعبارة اللحم المخصوص،
وسعر تسعة وثلاثين ريال.

النطق:
انطق كلمة نجدي بنطق سعودي طبيعي.
انطق كلمة رز بالطريقة السعودية الطبيعية.
انطق أسماء التطبيقات بوضوح:
جاهز، هنقرستيشن، نينجا.

اقرأ النص المكتوب فقط.
لا تضف مقدمة أو خاتمة أو شرحًا.
لا تضف موسيقى أو مؤثرات صوتية.
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