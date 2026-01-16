FROM node:20-alpine as builder

WORKDIR /app

# Accept build arg
ARG REACT_APP_BACKEND_URL=http://localhost:8001
ENV REACT_APP_BACKEND_URL=$REACT_APP_BACKEND_URL

# Copy package files
COPY package.json ./

# Install dependencies
RUN yarn install

# Copy source
COPY . .

# Build
RUN yarn build

# Production stage
FROM node:20-alpine

WORKDIR /app

RUN yarn global add serve

COPY --from=builder /app/build ./build

EXPOSE 3006

CMD ["serve", "-s", "build", "-l", "3006"]
