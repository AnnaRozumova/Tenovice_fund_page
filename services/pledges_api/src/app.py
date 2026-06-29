"""FastAPI app for the pledges API + the Lambda (Mangum) entrypoint.

One Lambda runs this whole app behind a single API Gateway ``ANY /{proxy+}`` route
(decision D19): every endpoint is a route here, and shared concerns — DynamoDB
access (``db``), response encoding (``utils.http``), validation and pledge math
(``domain``) — are imported once instead of duplicated per handler. ``handler`` is
the Mangum adapter that turns the Lambda event into an ASGI call into ``app``.

Routes (unchanged contract vs the old per-endpoint Lambdas):
  GET  /stats              POST /pledges            GET  /config
  GET  /pledges            GET  /pledges/by-email   POST /config
  POST /calculate
"""
from fastapi import FastAPI, Response
from mangum import Mangum

from api.calculate import router as calculate_router
from api.config import router as config_router
from api.pledges import router as pledges_router
from api.stats import router as stats_router

# redirect_slashes=False: a trailing slash (e.g. POST /calculate/) should 404, not
# 307-redirect — a 307 on POST is a footgun (clients/CORS handle it inconsistently).
app = FastAPI(title="Tenovice pledges API", redirect_slashes=False)
app.include_router(stats_router)
app.include_router(pledges_router)
app.include_router(config_router)
app.include_router(calculate_router)


# CORS preflight. The single ``ANY /{proxy+}`` route forwards the browser's preflight
# ``OPTIONS`` into the app, where FastAPI has no OPTIONS handler and would return 405 —
# and a non-2xx preflight makes the browser block the real request (the calculator /
# save POSTs). API Gateway already decorates responses with the CORS headers
# (allow-origin / -methods / -headers), so we only need a 2xx status. Do it in
# middleware (not a catch-all OPTIONS route — that would register every path and make
# unknown paths 405 instead of 404); the gateway attaches the headers in front.
@app.middleware("http")
async def answer_cors_preflight(request, call_next):
    if request.method == "OPTIONS":
        return Response(status_code=204)
    return await call_next(request)


# Lambda entrypoint: Mangum adapts the API Gateway event ⇄ ASGI. CDK points the
# single Lambda's handler at ``app.handler``. lifespan="off": there are no
# startup/shutdown hooks, and Lambda has no use for the ASGI lifespan protocol.
handler = Mangum(app, lifespan="off")
