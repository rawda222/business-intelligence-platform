"""
Brand Foundation Prompt Rules
"""

from textwrap import dedent


BRAND_FOUNDATION_PROMPT_RULES = dedent(
    """
    BRAND STRATEGY FOUNDATION:

    In addition to the existing TOWS, priority actions, resources,
    and campaign outputs, return these top-level fields:

    - positioning
    - audience
    - value_proposition
    - tone_of_voice
    - content_pillars
    - channels
    - goals

    GROUNDING RULES:

    1. Every section and every list item must contain
       source_swot_item_ids.

    2. source_swot_item_ids must use only item IDs present in the
       supplied SWOT data.

    3. Never invent customer demographics, age groups, income,
       geography, behavior, or market segments.

    4. Audience descriptions must be based only on needs, pain
       points, and strategic implications supported by the SWOT.

    5. Never invent numerical revenue, engagement, conversion,
       growth, or market-share targets.

    6. Goals must use directional success_signals unless an
       explicit numeric target exists in the supplied data.

    7. Do not claim a channel is currently active unless the input
       source coverage supports that claim.

    8. Omit unsupported list entries. For unsupported singular
       sections, return empty strings, empty lists, and an empty
       source_swot_item_ids list.

    REQUIRED JSON SHAPE:

    {
      "positioning": {
        "statement": "",
        "category_focus": "",
        "differentiators": [],
        "reasoning": "",
        "source_swot_item_ids": []
      },
      "audience": [
        {
          "segment_name": "",
          "description": "",
          "needs": [],
          "pain_points": [],
          "message_focus": "",
          "priority": "primary",
          "source_swot_item_ids": []
        }
      ],
      "value_proposition": {
        "statement": "",
        "customer_value": [],
        "reasons_to_believe": [],
        "source_swot_item_ids": []
      },
      "tone_of_voice": {
        "traits": [],
        "do": [],
        "avoid": [],
        "rationale": "",
        "source_swot_item_ids": []
      },
      "content_pillars": [
        {
          "name": "",
          "purpose": "",
          "key_messages": [],
          "recommended_formats": [],
          "source_swot_item_ids": []
        }
      ],
      "channels": [
        {
          "channel": "",
          "role": "",
          "content_focus": [],
          "priority": "primary",
          "reasoning": "",
          "source_swot_item_ids": []
        }
      ],
      "goals": [
        {
          "goal": "",
          "goal_type": "",
          "priority": "high",
          "success_signals": [],
          "horizon": "short_term",
          "source_swot_item_ids": []
        }
      ]
    }
    """
).strip()