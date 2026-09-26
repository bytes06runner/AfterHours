# The bot explains itself, and anyone can check

Afterhours now runs end to end on a local chain: lenders deposit, the bot reads the vault,
forecasts the bad case for each stock over the next few closes, decides where the money should
sit, and moves it. For every move it writes a short reason card ("bad-case drop 4.1% plus margin
5.0% exceeds the 91.5% tier's cushion of 6.1%") and records the card's hash onchain.

The API serves the card in canonical JSON, so anyone can hash it again and compare it with the
registry event. Our automated test forces a closing bell and checks that funds moved exactly as
planned and that every card matches its onchain hash. Next: the scripted demo.
