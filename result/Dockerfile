FROM node:22.23.3-alpine3.24@sha256:0a7108bf6c7bf5de370ffb1a3ed6be93d405b43ff159f681a8d18c0e2bc2e402 AS base

# add curl for healthcheck
RUN apk add --no-cache curl tini

WORKDIR /usr/local/app

COPY package*.json ./

RUN npm ci --omit=dev && \
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

# The runtime invokes node directly; npm and npx are build tools and are not
# needed in the final image.
RUN rm -rf /usr/local/lib/node_modules/npm && \
    rm -f /usr/local/bin/npm /usr/local/bin/npx

COPY --chown=node:node . .

ENV NODE_ENV=production \
    PORT=8080 \
    NODE_PATH=/node_modules
EXPOSE 8080

ENTRYPOINT ["/sbin/tini", "--"]
USER node
CMD ["node", "server.js"]
