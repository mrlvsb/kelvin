from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter, ChannelNameRouter
import examinator.routing
import examinator.consumers

application = ProtocolTypeRouter({
    'websocket': AuthMiddlewareStack(
        URLRouter(
            examinator.routing.websocket_urlpatterns
        )
    ),
    'channel': ChannelNameRouter({
        'heartbeat': examinator.consumers.BeatConsumer,
    }),
})
