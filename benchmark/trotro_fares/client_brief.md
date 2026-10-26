Client: a station officer at a trotro station in Accra.

- A route links two stops (stop names as plain text, typed the same way each time) and has one fare in cedis, which may include pesewas (e.g. 7.50).
- Fares are the same in both directions. One route covers both ways; a passenger can look up A to B or B to A and gets the same route and fare.
- Passengers look up a fare by giving the two stop names.
- Only direct routes count. If there is no route between the two stops, the answer is "not found" (404); never combine routes.
- A route between two stops that already have one (in either direction) is refused.
- A fare must be more than zero, both when adding a route and when changing its fare. A refused change keeps the old fare.
- Changing the fare of a route that does not exist is "not found" (404).
- They want to see all routes. Deleting routes is not needed now.
