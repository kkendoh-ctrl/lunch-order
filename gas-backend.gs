/**
 * お昼の注文 - Google Apps Script バックエンド (v2.1)
 *
 * 【セットアップ手順】
 * 1. Googleドライブで新規スプレッドシートを作成（名前は何でもOK）
 * 2. メニューバー「拡張機能 → Apps Script」を開く
 * 3. このファイルの中身を全部コピペして保存（Ctrl+S）
 * 4. 右上「デプロイ → 新しいデプロイ」
 *    - 種類: ウェブアプリ
 *    - 説明: お昼の注文API
 *    - 次のユーザーとして実行: 自分
 *    - アクセスできるユーザー: 全員
 * 5. 「デプロイ」ボタン → 権限を承認
 * 6. 表示される「ウェブアプリのURL」をコピー
 * 7. index.htmlの「設定」タブに貼って保存
 *
 * 【コードを更新したとき】
 * 「デプロイ → デプロイを管理 → 鉛筆アイコン → バージョン:新バージョン → デプロイ」
 * （URLは変わりません）
 *
 * 【v2.1 で追加】
 *  - 注文時メモ（ご飯少なめ等）  → orders シートに note 列追加
 *  - 数量制限（人気弁当の上限）  → menu の各品に limit 追加、超過時はエラー
 *  - 既存スプレッドシートは自動で列追加マイグレーション
 */

const SHEET_SESSIONS = 'sessions';
const SHEET_ORDERS = 'orders';

function doPost(e) {
  try {
    const body = JSON.parse(e.postData.contents);
    const action = body.action;
    let result;
    switch (action) {
      case 'createSession': result = createSession(body); break;
      case 'getSession':    result = getSession(body); break;
      case 'submitOrder':   result = submitOrder(body); break;
      case 'getOrders':     result = getOrders(body); break;
      default: throw new Error('unknown action: ' + action);
    }
    return jsonResponse(result);
  } catch (err) {
    return jsonResponse({ error: err.message });
  }
}

function doGet(e) {
  return jsonResponse({ ok: true, message: 'お昼の注文API稼働中', version: '2.1' });
}

function jsonResponse(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

function getSheet(name, headers) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sh = ss.getSheetByName(name);
  if (!sh) {
    sh = ss.insertSheet(name);
    sh.getRange(1, 1, 1, headers.length).setValues([headers]);
    sh.setFrozenRows(1);
  } else {
    // 既存シートに新規列が増えた場合のマイグレーション
    const currentHeaders = sh.getRange(1, 1, 1, sh.getLastColumn() || 1).getValues()[0];
    const missing = headers.slice(currentHeaders.length);
    if (missing.length > 0) {
      sh.getRange(1, currentHeaders.length + 1, 1, missing.length).setValues([missing]);
    }
  }
  return sh;
}

function sessionsSheet() {
  return getSheet(SHEET_SESSIONS, ['sessionId', 'shop', 'deadline', 'menuJson', 'createdAt']);
}
function ordersSheet() {
  // v2.1: note 列を追加
  return getSheet(SHEET_ORDERS, ['sessionId', 'name', 'item', 'timestamp', 'note']);
}

function createSession(body) {
  const sh = sessionsSheet();
  const sessionId = Utilities.getUuid().slice(0, 8);
  sh.appendRow([
    sessionId,
    body.shop || '',
    body.deadline || '',
    JSON.stringify(body.menu || []),  // menu 各品に limit を含めて保存
    new Date().toISOString()
  ]);
  return { sessionId };
}

function getSession(body) {
  const sh = sessionsSheet();
  const data = sh.getDataRange().getValues();
  for (let i = 1; i < data.length; i++) {
    if (data[i][0] === body.sessionId) {
      return {
        sessionId: data[i][0],
        shop: data[i][1],
        deadline: data[i][2],
        menu: JSON.parse(data[i][3] || '[]')
      };
    }
  }
  throw new Error('セッションが見つかりません');
}

function submitOrder(body) {
  // セッション存在チェック＋締切チェック＋数量制限チェック
  const sessions = sessionsSheet().getDataRange().getValues();
  let session = null;
  for (let i = 1; i < sessions.length; i++) {
    if (sessions[i][0] === body.sessionId) {
      const deadline = sessions[i][2];
      if (deadline && new Date(deadline) < new Date()) {
        throw new Error('受付は締め切られました');
      }
      session = {
        shop: sessions[i][1],
        menu: JSON.parse(sessions[i][3] || '[]')
      };
      break;
    }
  }
  if (!session) throw new Error('セッションが見つかりません');

  const sh = ordersSheet();
  const data = sh.getDataRange().getValues();

  // 数量制限チェック（このメニューにlimitがあれば、現在の注文数を確認）
  const targetMenu = session.menu.find(m => m.name === body.item);
  if (targetMenu && targetMenu.limit) {
    let currentCount = 0;
    for (let i = 1; i < data.length; i++) {
      if (data[i][0] === body.sessionId && data[i][2] === body.item) {
        // 同じ人の上書きはカウントしない
        if (data[i][1] !== body.name) currentCount++;
      }
    }
    if (currentCount >= Number(targetMenu.limit)) {
      throw new Error(`「${body.item}」は売り切れました（上限${targetMenu.limit}個）`);
    }
  }

  // 同じ名前があれば上書き
  for (let i = 1; i < data.length; i++) {
    if (data[i][0] === body.sessionId && data[i][1] === body.name) {
      sh.getRange(i + 1, 3).setValue(body.item);
      sh.getRange(i + 1, 4).setValue(new Date().toISOString());
      sh.getRange(i + 1, 5).setValue(body.note || '');
      return { ok: true, updated: true };
    }
  }
  sh.appendRow([body.sessionId, body.name, body.item, new Date().toISOString(), body.note || '']);
  return { ok: true };
}

function getOrders(body) {
  const sh = ordersSheet();
  const data = sh.getDataRange().getValues();
  const orders = [];
  for (let i = 1; i < data.length; i++) {
    if (data[i][0] === body.sessionId) {
      orders.push({
        name: data[i][1],
        item: data[i][2],
        timestamp: data[i][3],
        note: data[i][4] || ''
      });
    }
  }
  return { orders };
}
