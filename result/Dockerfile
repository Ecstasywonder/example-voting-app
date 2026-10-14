FROM node:22.22.0-bookworm-slim@sha256:dd9d21971ec4395903fa6143c2b9267d048ae01ca6d3ea96f16cb30df6187d94 AS base

# add curl for healthcheck
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl tini && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /usr/local/app

COPY package*.json ./

RUN npm ci && \
 npm cache clean --force && \
 mv /usr/local/app/node_modules /node_modules && \
 chown -R node:node /node_modules

FROM base AS dev

# Nodemon is needed only by the bind-mounted development target.
RUN npm install -g nodemon

ENV PORT=8080 \
    NODE_PATH=/node_modules

USER node

CMD ["nodemon", "--inspect=0.0.0.0", "server.js"]

FROM base AS final

COPY --chown=node:node . .

ENV NODE_ENV=production \
    PORT=8080 \
    NODE_PATH=/node_modules
EXPOSE 8080

ENTRYPOINT ["/usr/bin/tini", "--"]
USER node
CMD ["node", "server.js"]
