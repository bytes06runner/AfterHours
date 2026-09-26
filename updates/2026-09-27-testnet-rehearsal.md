# A dress rehearsal on both testnets

Before spending real testnet ETH, we rehearsed the whole deployment on copies of Robinhood Chain
testnet and Arbitrum Sepolia: a local node forks each chain at its latest block, and the same
commands we will run for real deploy the vault and its ten markets, create simulated lenders and
borrowers with their own keys, and run one cycle of the bot.

Both chains came out the same: five lenders, six borrowers, the vault allocated. The deployer
spent about 0.0065 ETH on each, so the real deployments need very little from the faucets. What
is left is creating and funding those keys and choosing where to host the app.
