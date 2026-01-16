from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models import UploadTask, UploadChunk, File, db
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os
import shutil
import uuid
import json

# API蓝图
api_bp = Blueprint('api', __name__)

@api_bp.route('/files/upload/create', methods=['POST'])
@login_required
def create_upload_task():
    """创建分块上传任务"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': '缺少请求数据'}), 400

        required_fields = ['hash', 'file_name', 'file_size', 'content_type']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'缺少必需字段: {field}'}), 400

        file_hash = data['hash']
        file_name = data['file_name']
        file_size = int(data['file_size'])
        content_type = data['content_type']

        # 获取分享选项
        share_type = data.get('share_type', 'link_only')
        allow_view = data.get('allow_view', True)
        allow_download = data.get('allow_download', True)
        allow_edit = data.get('allow_edit', False)
        password = data.get('password')
        expiry_type = data.get('expiry_type', 'never')
        expiry_hours = data.get('expiry_hours')
        custom_expiry = data.get('custom_expiry')
        allowed_users = data.get('allowed_users')

        # 检查用户限制
        if file_size > current_user.max_file_size:
            return jsonify({'error': f'文件大小超过限制 ({current_user.max_file_size // (1024*1024)}MB)'}), 400

        current_total_size = current_user.get_total_files_size()
        if current_total_size + file_size > current_user.max_total_size:
            return jsonify({'error': '上传后将超过总文件大小限制'}), 400

        current_files_count = current_user.get_total_files_count()
        if current_files_count >= current_user.max_total_files:
            return jsonify({'error': '已达到总文件数量限制'}), 400

        # 检查是否已有相同哈希的文件
        existing_file = File.query.filter_by(user_id=current_user.id).filter(
            File.filename.like(f'%{file_hash}%')
        ).first()

        if existing_file:
            # 检查文件是否完整
            try:
                if os.path.getsize(existing_file.filepath) == file_size:
                    return jsonify({
                        'file_exists': True,
                        'file': {
                            'id': existing_file.id,
                            'filename': existing_file.original_filename,
                            'size': os.path.getsize(existing_file.filepath),
                            'upload_time': existing_file.upload_time.isoformat()
                        }
                    }), 200
            except:
                pass

        # 检查是否已有进行中的上传任务
        existing_task = UploadTask.query.filter_by(
            user_id=current_user.id,
            file_hash=file_hash,
            status='uploading'
        ).first()

        if existing_task:
            return jsonify({
                'file_exists': False,
                'task_id': existing_task.id,
                'chunk_size': existing_task.chunk_size,
                'chunks_count': existing_task.chunks_count
            }), 200

        # 创建新的上传任务
        chunk_size = int(data.get('chunk_size', 5 * 1024 * 1024))  # 默认5MB
        chunks_count = (file_size + chunk_size - 1) // chunk_size  # 向上取整

        expired_at = None
        if 'expired_at' in data and data['expired_at']:
            try:
                expired_at = datetime.fromisoformat(data['expired_at'].replace('Z', '+00:00'))
            except:
                pass

        # 处理过期时间
        expiry_time = None
        if expiry_type == 'hours' and expiry_hours:
            try:
                expiry_time = datetime.utcnow() + timedelta(hours=int(expiry_hours))
            except ValueError:
                pass
        elif expiry_type == 'custom' and custom_expiry:
            try:
                expiry_time = datetime.strptime(custom_expiry, '%Y-%m-%d %H:%M')
            except ValueError:
                pass

        # 处理允许用户列表
        allowed_users_json = None
        if share_type == 'specified_users' and allowed_users:
            allowed_users_list = [u.strip() for u in allowed_users.split('\n') if u.strip()]
            allowed_users_json = json.dumps(allowed_users_list)

        # 存储分享选项到metadata
        metadata = {
            'share_type': share_type,
            'allow_view': allow_view,
            'allow_download': allow_download,
            'allow_edit': allow_edit,
            'password': password,
            'expiry_time': expiry_time.isoformat() if expiry_time else None,
            'allowed_users': allowed_users_json
        }

        new_task = UploadTask(
            user_id=current_user.id,
            file_hash=file_hash,
            file_name=file_name,
            file_size=file_size,
            content_type=content_type,
            chunk_size=chunk_size,
            chunks_count=chunks_count,
            pool_id=data.get('pool_id'),
            bundle_id=data.get('bundle_id'),
            encrypt_password=data.get('encrypt_password'),
            expired_at=expired_at,
            share_options=json.dumps(metadata)
        )

        db.session.add(new_task)
        db.session.commit()

        return jsonify({
            'file_exists': False,
            'task_id': new_task.id,
            'chunk_size': chunk_size,
            'chunks_count': chunks_count
        }), 200

    except Exception as e:
        # 记录详细错误到日志，但返回用户友好的错误信息
        import logging
        logging.error(f"创建上传任务失败: {str(e)}", exc_info=True)
        return jsonify({'error': '服务器内部错误，请稍后重试'}), 500

@api_bp.route('/files/upload/chunk/<task_id>/<int:chunk_index>', methods=['POST'])
@login_required
def upload_chunk(task_id, chunk_index):
    """上传文件分块"""
    try:
        task = UploadTask.query.filter_by(id=task_id, user_id=current_user.id).first()
        if not task:
            return jsonify({'error': '上传任务不存在'}), 404

        if task.status != 'uploading':
            return jsonify({'error': '上传任务已完成或失败'}), 400

        if chunk_index < 0 or chunk_index >= task.chunks_count:
            return jsonify({'error': '分块索引无效'}), 400

        # 检查分块是否已上传
        existing_chunk = UploadChunk.query.filter_by(task_id=task_id, chunk_index=chunk_index).first()
        if existing_chunk:
            return '', 200  # 分块已存在，直接返回成功

        # 获取上传的分块数据
        chunk_data = request.get_data()
        chunk_size = len(chunk_data)

        # 验证分块大小
        expected_size = task.chunk_size if chunk_index < task.chunks_count - 1 else (task.file_size % task.chunk_size or task.chunk_size)
        if chunk_size != expected_size:
            return jsonify({'error': f'分块大小不正确，期望 {expected_size} 字节，实际 {chunk_size} 字节'}), 400

        # 创建临时目录存储分块
        from flask import current_app
        upload_dir = current_app.config['UPLOAD_FOLDER']
        temp_dir = os.path.join(upload_dir, 'temp', task_id)
        os.makedirs(temp_dir, exist_ok=True)

        # 保存分块
        chunk_path = os.path.join(temp_dir, f'chunk_{chunk_index:06d}')
        with open(chunk_path, 'wb') as f:
            f.write(chunk_data)

        # 记录分块信息
        new_chunk = UploadChunk(
            task_id=task_id,
            chunk_index=chunk_index,
            chunk_size=chunk_size
        )
        db.session.add(new_chunk)
        db.session.commit()

        return '', 200

    except Exception as e:
        # 记录详细错误到日志，但返回用户友好的错误信息
        import logging
        logging.error(f"上传分块失败: {str(e)}", exc_info=True)
        return jsonify({'error': '服务器内部错误，请稍后重试'}), 500

@api_bp.route('/files/upload/complete/<task_id>', methods=['POST'])
@login_required
def complete_upload(task_id):
    """完成分块上传"""
    try:
        task = UploadTask.query.filter_by(id=task_id, user_id=current_user.id).first()
        if not task:
            return jsonify({'error': '上传任务不存在'}), 404

        if task.status != 'uploading':
            return jsonify({'error': '上传任务已完成或失败'}), 400

        # 检查所有分块是否已上传
        uploaded_chunks = UploadChunk.query.filter_by(task_id=task_id).count()
        if uploaded_chunks != task.chunks_count:
            return jsonify({'error': f'分块不完整，已上传 {uploaded_chunks}/{task.chunks_count}'}), 400

        # 合并分块
        from flask import current_app
        upload_dir = current_app.config['UPLOAD_FOLDER']
        temp_dir = os.path.join(upload_dir, 'temp', task_id)
        final_filename = str(uuid.uuid4()) + '_' + secure_filename(task.file_name)
        final_path = os.path.join(upload_dir, final_filename)

        # 确保uploads目录存在
        os.makedirs(upload_dir, exist_ok=True)

        # 检查temp目录是否存在
        if not os.path.exists(temp_dir):
            # temp目录不存在，标记任务失败并要求重新上传
            task.status = 'failed'
            db.session.commit()
            return jsonify({'error': '分块文件已丢失，请重新上传文件'}), 400

        with open(final_path, 'wb') as final_file:
            for i in range(task.chunks_count):
                chunk_path = os.path.join(temp_dir, f'chunk_{i:06d}')
                if not os.path.exists(chunk_path):
                    # 清理已创建的文件
                    if os.path.exists(final_path):
                        os.remove(final_path)
                    # 标记任务失败
                    task.status = 'failed'
                    db.session.commit()
                    raise Exception(f'分块文件不存在: {chunk_path}')
                with open(chunk_path, 'rb') as chunk_file:
                    final_file.write(chunk_file.read())

        # 验证文件大小
        actual_size = os.path.getsize(final_path)
        if actual_size != task.file_size:
            os.remove(final_path)
            raise Exception(f'文件大小不匹配，期望 {task.file_size} 字节，实际 {actual_size} 字节')

        # 从share_options获取分享选项
        metadata = json.loads(task.share_options) if task.share_options else {}
        share_type = metadata.get('share_type', 'link_only')
        allow_view = metadata.get('allow_view', True)
        allow_download = metadata.get('allow_download', True)
        allow_edit = metadata.get('allow_edit', False)
        password = metadata.get('password')
        expiry_time_str = metadata.get('expiry_time')
        allowed_users = metadata.get('allowed_users')

        expiry_time = None
        if expiry_time_str:
            try:
                expiry_time = datetime.fromisoformat(expiry_time_str)
            except:
                pass

        # 创建文件记录
        new_file = File(
            filename=final_filename,
            original_filename=task.file_name,
            raw_filename=task.file_name,  # 保存原始文件名
            filepath=final_path,
            user_id=current_user.id,
            is_public=(share_type == 'public'),
            share_type=share_type,
            allow_view=allow_view,
            allow_download=allow_download,
            allow_edit=allow_edit,
            password=password,
            expiry_time=expiry_time,
            allowed_users=allowed_users
        )
        db.session.add(new_file)

        # 更新任务状态
        task.status = 'completed'
        db.session.commit()

        # 立即清理临时分块文件
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
            # 记录清理失败，但不影响上传成功
            import logging
            logging.warning(f"清理临时文件失败: {temp_dir}, 错误: {str(e)}")

        return jsonify({
            'file_id': new_file.id,
            'filename': new_file.original_filename,
            'size': actual_size
        }), 200

    except Exception as e:
        # 记录详细错误到日志，但返回用户友好的错误信息
        import logging
        logging.error(f"完成上传失败: {str(e)}", exc_info=True)
        return jsonify({'error': '服务器内部错误，请稍后重试'}), 500
