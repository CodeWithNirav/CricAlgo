#!/usr/bin/env python3
import asyncio
import httpx

async def test_register():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            'http://app:8000/api/v1/register',
            json={'username': 'smoke_user_a_1758295117', 'telegram_id': 1001}
        )
        print(f'Status: {response.status_code}')
        print(f'Response: {response.text}')

if __name__ == "__main__":
    asyncio.run(test_register())
