"""Kafka 브로커 설정"""

import logging
import ssl

from faststream.kafka import KafkaBroker
from faststream.security import SASLOAuthBearer

from src.conf.settings import settings

logger = logging.getLogger(__name__)


def _get_connection_kwargs() -> dict:
    """aiokafka 연결 공통 kwargs"""
    if not settings.kafka_use_iam:
        return {"bootstrap_servers": settings.kafka_bootstrap_servers}

    from aiokafka.abc import AbstractTokenProvider
    from aws_msk_iam_sasl_signer import MSKAuthTokenProvider

    class MSKTokenProvider(AbstractTokenProvider):
        async def token(self):
            token, _ = MSKAuthTokenProvider.generate_auth_token(settings.aws_region)
            return token

    return {
        "bootstrap_servers": settings.kafka_bootstrap_servers,
        "security_protocol": "SASL_SSL",
        "sasl_mechanism": "OAUTHBEARER",
        "sasl_oauth_token_provider": MSKTokenProvider(),
        "ssl_context": ssl.create_default_context(),
    }


def _create_broker() -> KafkaBroker:
    """Kafka 브로커 생성"""
    kwargs = _get_connection_kwargs()
    if settings.kafka_use_iam:
        return KafkaBroker(
            kwargs["bootstrap_servers"],
            security=SASLOAuthBearer(ssl_context=kwargs["ssl_context"]),
            sasl_oauth_token_provider=kwargs["sasl_oauth_token_provider"],
        )
    return KafkaBroker(kwargs["bootstrap_servers"])


async def ensure_topics(topics: list[str]) -> None:
    """토픽이 존재하지 않으면 생성"""
    from aiokafka.admin import AIOKafkaAdminClient, NewTopic

    admin = AIOKafkaAdminClient(**_get_connection_kwargs())
    try:
        await admin.start()
        existing = await admin.list_topics()
        new_topics = [NewTopic(name=t, num_partitions=1, replication_factor=1) for t in topics if t not in existing]
        if new_topics:
            await admin.create_topics(new_topics)
            logger.info(f"Created topics: {[t.name for t in new_topics]}")
    finally:
        await admin.close()


broker = _create_broker()
