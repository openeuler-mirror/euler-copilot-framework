FROM hub.oepkgs.net/neocopilot/framework-baseimg:0.10.0-x86

ENV PYTHONPATH=/app
ENV TIKTOKEN_CACHE_DIR=/app/assets/tiktoken

COPY --chmod=550 ./ /app/
RUN chmod 766 /root

CMD ["uv", "run", "--no-sync", "--no-dev", "apps/main.py"]
