Client: the owner of a shop in Accra who wants a simple wallet for regular customers.

- A wallet belongs to one customer: name and phone number. One wallet per phone number; a second wallet for the same number is refused.
- A new wallet has a balance of 0.
- Customers can deposit into their wallet and transfer to another wallet. No withdrawals, fees or limits for now.
- Amounts are in cedis with at most 2 decimal places (pesewas) and must be more than 0.
- A transfer is refused if the sender does not have enough; balances never go below 0. Transfers to the same wallet are refused. A refused transfer changes nothing.
- Arithmetic must be exact to the pesewa (e.g. 0.70 + 0.10 is exactly 0.80).
- Each wallet has a history of deposits, transfers out and transfers in, each with the amount and the balance right after it.
