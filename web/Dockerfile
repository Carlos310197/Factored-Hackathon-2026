# NEXT_PUBLIC_* values are inlined into the client bundle at build time, so they are build args, not runtime env.
FROM --platform=linux/amd64 public.ecr.aws/docker/library/node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG NEXT_PUBLIC_GIT_SHA=
ARG NEXT_PUBLIC_EVENTS_HTTP_DOMAIN=
ARG NEXT_PUBLIC_EVENTS_REGION=us-east-1
ENV NEXT_PUBLIC_GIT_SHA=$NEXT_PUBLIC_GIT_SHA \
    NEXT_PUBLIC_EVENTS_HTTP_DOMAIN=$NEXT_PUBLIC_EVENTS_HTTP_DOMAIN \
    NEXT_PUBLIC_EVENTS_REGION=$NEXT_PUBLIC_EVENTS_REGION
RUN npm run build

FROM --platform=linux/amd64 public.ecr.aws/docker/library/node:22-alpine
WORKDIR /app
ENV NODE_ENV=production PORT=3000 HOSTNAME=0.0.0.0
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
USER node
EXPOSE 3000
CMD ["node", "server.js"]
