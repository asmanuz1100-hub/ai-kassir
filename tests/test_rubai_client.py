"""RubaiSTT integration tests: no network, model downloads, or real credentials."""
import os
import unittest
from unittest.mock import patch

import httpx
import rubai_client

class RubaiClientTests(unittest.IsolatedAsyncioTestCase):
    def test_not_configured_leaves_groq_untouched(self):
        with patch.dict(os.environ, {"RUBAI_ASR_URL": "", "RUBAI_ASR_TOKEN": ""}):
            self.assertFalse(rubai_client.rubai_ready())

    def test_https_required(self):
        for url in ("http://remote.example", "https://user:pass@remote.example",
                    "https://remote.example/?token=123", "https://remote.example/redirect"):
            with self.assertRaises(rubai_client.RubaiUnavailable):
                rubai_client.checked_endpoint(url)

    async def test_remote_uzbek_text(self):
        seen = {}
        def handler(request):
            seen['path']=request.url.path
            seen['auth']=request.headers.get('Authorization')
            return httpx.Response(200, json={"text":"Наманган Фурқатдан беш юз доллар олдим","model":"rubaistt_v2_medium"})
        transport=httpx.MockTransport(handler)
        original=httpx.AsyncClient
        # Avoid replacing the httpx.AsyncClient constructor with a recursive mock.
        def factory(*args, **kwargs):
            kwargs['transport']=transport
            return original(*args, **kwargs)
        with patch.dict(os.environ, {"RUBAI_ASR_URL":"https://private.example","RUBAI_ASR_TOKEN":"test-secret"}), patch.object(rubai_client.httpx,"AsyncClient",side_effect=factory):
            result=await rubai_client.rubai_transcribe(b"fake synthetic audio")
        self.assertIn("Фурқатдан",result)
        self.assertEqual(seen['path'],"/transcribe")
        self.assertEqual(seen['auth'],"Bearer test-secret")

    async def test_service_error_is_clear(self):
        original=httpx.AsyncClient
        def factory(*args, **kwargs):
            return original(*args, transport=httpx.MockTransport(lambda request: httpx.Response(503)))
        with patch.dict(os.environ, {"RUBAI_ASR_URL":"https://private.example","RUBAI_ASR_TOKEN":"test-secret"}), patch.object(rubai_client.httpx,"AsyncClient",side_effect=factory):
            with self.assertRaises(rubai_client.RubaiUnavailable):
                await rubai_client.rubai_transcribe(b"synthetic audio")

if __name__=="__main__":
    unittest.main()
