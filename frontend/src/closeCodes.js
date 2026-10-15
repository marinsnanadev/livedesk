export const CLOSE_BAD_REQUEST = 4400
export const CLOSE_UNAUTHORIZED = 4401
export const CLOSE_NOT_FOUND = 4404

const SERVER_REJECTIONS = [CLOSE_BAD_REQUEST, CLOSE_UNAUTHORIZED, CLOSE_NOT_FOUND]

// A rejection is the server saying "no" on purpose, so retrying the same
// request would just fail again forever. Any other close is a dropped
// connection and is worth reconnecting.
export function isRejection(code) {
  return SERVER_REJECTIONS.includes(code)
}
