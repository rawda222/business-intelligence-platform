"""
Trends API Integration Tests

Verifies the trend endpoints across the full stack:

- Real user, business, and social account.
- Real social post + snapshots via services.
- Real customer review via services.
- Authentication and business ownership.
- Tenant isolation.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_current_user
from app.db.mongo import close_mongo, connect_to_mongo
from app.db.postgres import async_session_maker
from app.main import app
from app.models.mongo.customer_review import (
    CustomerReviewDocument,
)
from app.models.mongo.post_metric_snapshot import (
    PostMetricSnapshotDocument,
)
from app.models.mongo.social_post import (
    SocialPostDocument,
    SocialPostMetrics,
)
from app.models.pg.business import Business
from app.models.pg.user import User
from app.services.customer_review_storage_service import (
    build_customer_review_deduplication_key,
    create_customer_review,
)
from app.services.post_metric_service import (
    record_metric_snapshot,
)


@pytest.mark.asyncio
async def test_trends_api_end_to_end():
    """
    Exercise the full trend API for a real business.
    """

    unique_suffix = uuid4().hex

    business_id = None
    other_business_id = None
    user_id = None
    other_user_id = None

    social_account_id = uuid4()

    stored_post_id = None
    stored_review_id = None

    selected_user = {
        "value": None,
    }

    async def override_get_current_user():
        return selected_user["value"]

    try:
        await connect_to_mongo()

        # ============================================
        # 1. Create Users + Businesses in PostgreSQL
        # ============================================
        async with async_session_maker() as db:
            owner_user = User(
                email=(
                    "trends-owner-"
                    f"{unique_suffix}"
                    "@example.test"
                ),
                hashed_password=(
                    "trends-test-password"
                ),
                full_name="Trends Owner",
                is_active=True,
                is_verified=True,
                role="user",
            )

            other_user = User(
                email=(
                    "trends-other-"
                    f"{unique_suffix}"
                    "@example.test"
                ),
                hashed_password=(
                    "trends-test-password"
                ),
                full_name="Trends Other",
                is_active=True,
                is_verified=True,
                role="user",
            )

            db.add_all(
                [owner_user, other_user],
            )

            await db.commit()

            await db.refresh(owner_user)
            await db.refresh(other_user)

            user_id = owner_user.id
            other_user_id = other_user.id

            business = Business(
                owner_id=owner_user.id,
                name=(
                    "Trends Test Business "
                    f"{unique_suffix}"
                ),
                business_type="test_business",
                industry="testing",
                location="port-said",
                country_code="EG",
                business_metadata={
                    "test_record": True,
                },
                is_active=True,
            )

            other_business = Business(
                owner_id=other_user.id,
                name=(
                    "Trends Other Business "
                    f"{unique_suffix}"
                ),
                business_type="test_business",
                industry="testing",
                location="port-said",
                country_code="EG",

                business_metadata={
                    "test_record": True,
                },
                is_active=True,
            )

            db.add_all(
                [business, other_business],
            )

            await db.commit()

            await db.refresh(business)
            await db.refresh(other_business)

            business_id = business.id
            other_business_id = (
                other_business.id
            )

        # ============================================
        # 2. Create a Post + Metric Snapshots
        # ============================================
        published_at = datetime(
            2026,
            7,
            7,
            9,
            0,
            tzinfo=UTC,
        )

        post = SocialPostDocument(
            business_id=business_id,
            social_account_id=(
                social_account_id
            ),
            platform="facebook",
            platform_post_id=(
                f"trend-post-{unique_suffix}"
            ),
            published_at=published_at,
            content_type="text",
            text="Trend endpoint post",
            connector_type="apify",
            raw_data={
                "source": (
                    "trend_api_test"
                ),
            },
        )

        await post.insert()

        stored_post_id = post.id

        first_capture_at = (
            published_at + timedelta(hours=2)
        )

        second_capture_at = (
            published_at + timedelta(hours=8)
        )

        await record_metric_snapshot(
            business_id=business_id,
            social_account_id=(
                social_account_id
            ),
            social_post_id=stored_post_id,
            metrics=SocialPostMetrics(
                likes=None,
                reactions=10,
                comments=1,
                shares=0,
                views=50,
            ),
            captured_at=first_capture_at,
        )

        await record_metric_snapshot(
            business_id=business_id,
            social_account_id=(
                social_account_id
            ),
            social_post_id=stored_post_id,
            metrics=SocialPostMetrics(
                likes=None,
                reactions=25,
                comments=3,
                shares=1,
                views=120,
            ),
            captured_at=second_capture_at,
        )

        # ============================================
        # 3. Create a Customer Review
        # ============================================
        from app.schemas.normalized_social import (
            NormalizedCustomerReview,
        )

        review = NormalizedCustomerReview(
            business_id=business_id,
            source="google_maps",
            source_review_id=(
                "trend-review-"
                f"{unique_suffix}"
            ),
            text=(
                "خدمة ممتازة والقهوة رائعة"
            ),
            language="ar",
            rating=5.0,
            published_at=datetime(
                2026,
                7,
                5,
                18,
                0,
                tzinfo=UTC,
            ),
            collected_at=datetime(
                2026,
                7,
                5,
                20,
                0,
                tzinfo=UTC,
            ),
            information_quality="high",
            is_meaningful=True,
            is_emoji_only=False,
            raw_data={
                "source": (
                    "trend_api_test"
                ),
            },
        )

        stored_review = (
            await create_customer_review(
                review=review,
                deduplication_key=(
                    build_customer_review_deduplication_key(
                        review,
                    )
                ),
            )
        )

        stored_review_id = stored_review.id

        # ============================================
        # 4. Configure Auth Override
        # ============================================
        app.dependency_overrides[
            get_current_user
        ] = override_get_current_user

        transport = ASGITransport(app=app)

        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            async with async_session_maker() as db:
                selected_user["value"] = (
                    await db.get(
                        User,
                        user_id,
                    )
                )

            # ========================================
            # A. Foundation Endpoint
            # ========================================
            foundation_response = (
                await client.get(
                    (
                        "/api/v1/businesses/"
                        f"{business_id}"
                        "/trends/foundation"
                    ),
                )
            )

            assert (
                foundation_response.status_code
                == 200
            )

            foundation_body = (
                foundation_response.json()
            )

            assert (
                foundation_body[
                    "total_posts"
                ]
                == 1
            )

            assert (
                foundation_body[
                    "total_customer_reviews"
                ]
                == 1
            )

            assert (
                foundation_body[
                    "posts_by_platform"
                ]
                == {
                    "facebook": 1,
                }
            )

            assert (
                foundation_body[
                    "reviews_by_source"
                ]
                == {
                    "google_maps": 1,
                }
            )

            # ========================================
            # B. Posts Per Week Endpoint
            # ========================================
            posts_response = (
                await client.get(
                    (
                        "/api/v1/businesses/"
                        f"{business_id}"
                        "/trends/"
                        "posts-per-week"
                    ),
                    params={
                        "range_start": (
                            "2026-07-06T00:00:00"
                            "+00:00"
                        ),
                        "range_end": (
                            "2026-07-27T00:00:00"
                            "+00:00"
                        ),
                    },
                )
            )

            assert (
                posts_response.status_code
                == 200
            )

            posts_body = posts_response.json()

            assert (
                posts_body["total_posts"]
                == 1
            )

            assert (
                len(posts_body["buckets"])
                == 3
            )

            # ========================================
            # C. Engagement Curve Endpoint
            # ========================================
            engagement_response = (
                await client.get(
                    (
                        "/api/v1/businesses/"
                        f"{business_id}"
                        "/posts/"
                        f"{stored_post_id}"
                        "/engagement-curve"
                    ),
                    params={
                        "social_account_id": (
                            str(
                                social_account_id,
                            )
                        ),
                        "range_start": (
                            "2026-07-07T00:00:00"
                            "+00:00"
                        ),
                        "range_end": (
                            "2026-07-11T00:00:00"
                            "+00:00"
                        ),
                    },
                )
            )

            assert (
                engagement_response
                .status_code
                == 200
            )

            engagement_body = (
                engagement_response.json()
            )

            assert (
                len(engagement_body["points"])
                >= 1
            )

            # ========================================
            # D. Reviews Per Month Endpoint
            # ========================================
            reviews_response = (
                await client.get(
                    (
                        "/api/v1/businesses/"
                        f"{business_id}"
                        "/trends/"
                        "reviews-per-month"
                    ),
                    params={
                        "range_start": (
                            "2026-07-01T00:00:00"
                            "+00:00"
                        ),
                        "range_end": (
                            "2026-08-01T00:00:00"
                            "+00:00"
                        ),
                    },
                )
            )

            assert (
                reviews_response.status_code
                == 200
            )

            reviews_body = (
                reviews_response.json()
            )

            assert (
                reviews_body["total_reviews"]
                == 1
            )

            assert (
                reviews_body["source"]
                == "google_maps"
            )

            assert (
                len(reviews_body["buckets"])
                == 1
            )

            assert (
                reviews_body["buckets"][0][
                    "rating_average"
                ]
                == 5.0
            )

            # ========================================
            # E. Cross-Tenant Isolation
            # ========================================
            async with async_session_maker() as db:
                selected_user["value"] = (
                    await db.get(
                        User,
                        other_user_id,
                    )
                )

            forbidden_response = (
                await client.get(
                    (
                        "/api/v1/businesses/"
                        f"{business_id}"
                        "/trends/foundation"
                    ),
                )
            )

            assert (
                forbidden_response.status_code
                == 404
            )

    finally:
        try:
            if stored_review_id is not None:
                stored_review = (
                    await CustomerReviewDocument
                    .get(
                        stored_review_id,
                    )
                )

                if stored_review is not None:
                    await stored_review.delete()

            if stored_post_id is not None:
                await (
                    PostMetricSnapshotDocument
                    .find(
                        PostMetricSnapshotDocument
                        .social_post_id
                        == stored_post_id,
                    )
                    .delete()
                )

                stored_post = (
                    await SocialPostDocument
                    .get(
                        stored_post_id,
                    )
                )

                if stored_post is not None:
                    await stored_post.delete()

            # ========================================
            # Delete PostgreSQL entities
            # ========================================
            async with async_session_maker() as db:
                if business_id is not None:
                    stored_business = (
                        await db.get(
                            Business,
                            business_id,
                        )
                    )

                    if stored_business is not None:
                        await db.delete(
                            stored_business,
                        )

                if other_business_id is not None:
                    stored_other_business = (
                        await db.get(
                            Business,
                            other_business_id,
                        )
                    )

                    if stored_other_business is not None:
                        await db.delete(
                            stored_other_business,
                        )

                if user_id is not None:
                    stored_user = (
                        await db.get(
                            User,
                            user_id,
                        )
                    )

                    if stored_user is not None:
                        await db.delete(
                            stored_user,
                        )

                if other_user_id is not None:
                    stored_other_user = (
                        await db.get(
                            User,
                            other_user_id,
                        )
                    )

                    if stored_other_user is not None:
                        await db.delete(
                            stored_other_user,
                        )

                await db.commit()
        finally:
            app.dependency_overrides.pop(
                get_current_user,
                None,
            )

            await close_mongo()
