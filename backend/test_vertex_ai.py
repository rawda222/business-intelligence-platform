"""
Quick test: Verify Vertex AI / Gemini connection.
Uses the new google-genai SDK.
"""


def test_vertex_ai():
    print("\n" + "=" * 60)
    print("  Vertex AI / Gemini Connection Test (New SDK)")
    print("=" * 60)
    
    try:
        from google import genai
        from app.core.config import settings
        
        print(f"\nProject: {settings.GOOGLE_CLOUD_PROJECT}")
        print(f"Location: {settings.VERTEX_AI_LOCATION}")
        print(f"Model: {settings.VERTEX_AI_MODEL}")
        
        # Create client (new SDK)
        client = genai.Client(
            vertexai=True,
            project=settings.GOOGLE_CLOUD_PROJECT,
            location=settings.VERTEX_AI_LOCATION,
        )
        
        # Test query
        print("\nSending test query to Gemini...")
        response = client.models.generate_content(
            model=settings.VERTEX_AI_MODEL,
            contents="Say 'Hello from Rawda!' in one short sentence.",
        )
        
        print(f"\n[OK] Vertex AI connected successfully!")
        print(f"Gemini says: {response.text}")
        
    except Exception as e:
        print(f"\n[FAIL] Vertex AI failed:")
        print(f"   {type(e).__name__}: {e}")


if __name__ == "__main__":
    test_vertex_ai()