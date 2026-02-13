export default {
	async fetch(request, env) {
		const url = new URL(request.url);
		if (url.pathname === "/health") return new Response("ok", { status: 200 });
		if (request.method !== "GET" && request.method !== "HEAD") {
			return new Response("Method Not Allowed", { status: 405 });
		}

		const key = url.pathname.replace(/^\//, "");
		if (!key) return new Response("Not Found", { status: 404 });

		try {
			const object = await env.TRAVELLAND.get(key);
			if (!object) return new Response("Not Found", { status: 404 });

			const headers = new Headers(object.httpMetadata?.headers || {});
			headers.set("Cache-Control", "public, max-age=31536000, immutable");

			return new Response(object.body, {
				status: 200,
				headers,
			});
		} catch (err) {
			console.error("[R2 proxy] error", err);
			return new Response("Upstream error", { status: 502 });
		}
	},
};
