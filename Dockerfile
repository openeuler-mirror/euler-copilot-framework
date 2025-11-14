FROM hub.oepkgs.net/neocopilot/framework_base:0.9.6-x86-test

ENV PYTHONPATH=/app
ENV TIKTOKEN_CACHE_DIR=/app/data/tiktoken_cache

COPY --chmod=550 ./ /app/
RUN chmod 766 /root

CMD ["uv", "run", "--no-sync", "python", "-m", "apps.main"]
