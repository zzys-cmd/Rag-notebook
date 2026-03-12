<template>
  <div class="profile-page">
    <van-nav-bar
      title="个人信息"
      left-arrow
      @click-left="$router.back()"
      fixed
    />
    
    <div class="profile-container">
      <van-cell-group inset class="avatar-group">
        <van-cell title="头像" center is-link @click="showAvatarDialog">
          <template #right-icon>
            <van-image
              round
              width="60"
              height="60"
              :src="userInfo?.avatar ? `http://192.168.0.114:8000/avatar/${userInfo.avatar}` : 'https://fastly.jsdelivr.net/npm/@vant/assets/cat.jpeg'"
            />
          </template>
        </van-cell>
      </van-cell-group>
      
      <van-cell-group inset class="info-group">
        <van-cell title="用户名" :value="userInfo.username || 'admin'" />
        <van-cell title="昵称" :value="userInfo.nickname || '暂无昵称'" is-link @click="showNicknameDialog" />
        <van-cell title="性别" :value="userInfo.gender || '未设置'" is-link @click="showGenderDialog" />
        <van-cell title="手机号" :value="userInfo.phone || '未设置'" is-link @click="showPhoneDialog" />
        <van-cell title="个人简介" :value="userBio || '暂无简介'" is-link @click="showBioDialog" />
      </van-cell-group>
      
      <van-cell-group inset class="security-group">
        <van-cell title="修改密码" is-link @click="showPasswordConfirm" />
      </van-cell-group>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, h, onMounted } from 'vue';
import { useUserStore } from '../store/user';
import { showDialog, showToast, showLoadingToast, showSuccessToast, showFailToast, Dialog, RadioGroup, Radio } from 'vant';
import { useRouter } from 'vue-router';
import axios from 'axios';
import { apiConfig } from '../config/api';

const router = useRouter();
const userStore = useUserStore();

// 初始化用户状态
onMounted(async () => {
  // 如果用户未登录，跳转到登录页面
  if (!userStore.getLoginStatus) {
    router.push('/login');
    return;
  }
  
  // 获取用户信息
  try {
    // 显示加载提示
    const loadingInstance = showLoadingToast({
      message: '加载中...',
      forbidClick: true,
      duration: 0
    });
    
    // console.log('获取用户信息，当前token:', userStore.token);
    
    // 使用新的 getUserInfoDetail 方法
    const result = await userStore.getUserInfoDetail();
    
    // 手动关闭加载提示
    loadingInstance.close();
    
    if (result.success) {
      console.log('获取用户信息成功:', userStore.userInfo);
      // 显示成功提示
      // showSuccessToast('获取用户信息成功');
    } else {
      console.error('获取用户信息失败:', result.message);
      showFailToast(result.message || '获取用户信息失败');
    }
  } catch (error) {
    console.error('获取用户信息请求失败:', error);
    // 确保关闭加载提示
    showToast.clear();
    showToast.fail('获取用户信息失败');
  }
});

const userInfo = computed(() => userStore.userInfo);
const userId = computed(() => userStore.token ? userStore.token.substring(0, 5) : '');
const userBio = computed(() => userStore.userInfo?.bio || '暂无简介');

const showPasswordConfirm = () => {
  // 使用ref创建响应式变量
  const oldPassword = ref('');
  const newPassword = ref('');
  const confirmPassword = ref('');
  
  showDialog({
    title: '修改密码',
    showCancelButton: true,
    className: 'password-dialog',
    message: h('div', { style: 'text-align: left; padding: 10px 0;' }, [
      h('div', { style: 'margin-bottom: 15px;' }, [
        h('div', { style: 'margin-bottom: 5px; text-align: left;' }, '当前密码：'),
        h('input', {
          type: 'password',
          value: oldPassword.value,
          onInput: (e) => { oldPassword.value = e.target.value },
          style: 'width: 100%; border: 1px solid #dcdee0; border-radius: 4px; padding: 8px; box-sizing: border-box;'
        })
      ]),
      h('div', { style: 'margin-bottom: 15px;' }, [
        h('div', { style: 'margin-bottom: 5px; text-align: left;' }, '新密码：'),
        h('input', {
          type: 'password',
          value: newPassword.value,
          onInput: (e) => { newPassword.value = e.target.value },
          style: 'width: 100%; border: 1px solid #dcdee0; border-radius: 4px; padding: 8px; box-sizing: border-box;'
        })
      ]),
      h('div', { style: 'margin-bottom: 15px;' }, [
        h('div', { style: 'margin-bottom: 5px; text-align: left;' }, '确认密码：'),
        h('input', {
          type: 'password',
          value: confirmPassword.value,
          onInput: (e) => { confirmPassword.value = e.target.value },
          style: 'width: 100%; border: 1px solid #dcdee0; border-radius: 4px; padding: 8px; box-sizing: border-box;'
        })
      ])
    ]),
  }).then(async () => {
    // 点击确认按钮
    if (!oldPassword.value) {
      showToast('请输入当前密码');
      return;
    }
    
    if (!newPassword.value) {
      showToast('请输入新密码');
      return;
    }
    
    if (newPassword.value !== confirmPassword.value) {
      showToast('两次密码输入不一致');
      return;
    }
    
    try {
      // 显示加载提示
      const loadingInstance = showLoadingToast({
        message: '修改中...',
        forbidClick: true,
        duration: 0
      });
      
      // 调用API更新密码
      const result = await userStore.updatePassword(oldPassword.value, newPassword.value);
      
      // 关闭加载提示
      loadingInstance.close();
      
      if (result && result.success) {
        showSuccessToast('密码修改成功');
      } else {
        showFailToast((result && result.message) || '密码修改失败');
      }
    } catch (error) {
      console.error('修改密码失败:', error);
      showToast.clear();
      showToast.fail('密码修改失败');
    }
  }).catch(() => {
    // 点击取消按钮
  });
};

const showBioDialog = () => {
  // 使用ref创建响应式变量
  const newBioValue = ref(userBio.value);
  
  showDialog({
    title: '修改个人简介',
    showCancelButton: true,
    confirmButtonText: '确认',
    className: 'bio-dialog',
    message: h('div', { style: 'text-align: left; padding: 10px 0;' }, [
      h('div', { style: 'margin-bottom: 15px;' }, [
        h('div', { style: 'margin-bottom: 5px; text-align: left;' }, '个人简介：'),
        h('textarea', {
          value: newBioValue.value,
          onInput: (e) => { newBioValue.value = e.target.value },
          style: 'width: 100%; border: 1px solid #dcdee0; border-radius: 4px; padding: 8px; box-sizing: border-box; min-height: 100px; resize: vertical;'
        })
      ])
    ])
  }).then(async () => {
    // 点击确认按钮
    try {
      // 显示加载提示
      const loadingInstance = showLoadingToast({
        message: '保存中...',
        forbidClick: true,
        duration: 0
      });
      
      console.log('更新个人简介:', newBioValue.value);
      
      // 调用API更新个人简介
      const result = await userStore.updateUserInfo({ bio: newBioValue.value });
      
      // 关闭加载提示
      loadingInstance.close();
      
      if (result && result.success) {
        showSuccessToast('个人简介修改成功');
      } else {
        showFailToast((result && result.message) || '个人简介修改失败');
      }
    } catch (error) {
      console.error('更新个人简介失败:', error);
      showToast.clear();
      showToast.fail('个人简介修改失败');
    }
  }).catch(() => {
    // 点击取消按钮
  });
};

const showNicknameDialog = () => {
  // 使用ref创建响应式变量
  const newNicknameValue = ref(userInfo.value?.nickname || '');
  
  showDialog({
    title: '修改昵称',
    showCancelButton: true,
    confirmButtonText: '确认',
    className: 'nickname-dialog',
    message: h('div', { style: 'text-align: left; padding: 10px 0;' }, [
      h('div', { style: 'margin-bottom: 15px;' }, [
        h('div', { style: 'margin-bottom: 5px; text-align: left;' }, '昵称：'),
        h('input', {
          type: 'text',
          value: newNicknameValue.value,
          onInput: (e) => { newNicknameValue.value = e.target.value },
          style: 'width: 100%; border: 1px solid #dcdee0; border-radius: 4px; padding: 8px; box-sizing: border-box;'
        })
      ])
    ])
  }).then(async () => {
    // 点击确认按钮
    try {
      // 显示加载提示
      const loadingInstance = showLoadingToast({
        message: '保存中...',
        forbidClick: true,
        duration: 0
      });
      
      console.log('更新昵称:', newNicknameValue.value);
      
      // 调用API更新昵称
      const result = await userStore.updateUserInfo({ nickname: newNicknameValue.value });
      
      // 关闭加载提示
      loadingInstance.close();
      
      if (result && result.success) {
        showSuccessToast('昵称修改成功');
      } else {
        showFailToast((result && result.message) || '昵称修改失败');
      }
    } catch (error) {
      console.error('更新昵称失败:', error);
      showToast.clear();
      showToast.fail('昵称修改失败');
    }
  }).catch(() => {
    // 点击取消按钮
  });
};

const showGenderDialog = () => {
  // 使用ref创建响应式变量
  const selectedGender = ref(userInfo.value?.gender || '男');
  
  // 使用Vant的Dialog组件显示性别选择
  showDialog({
    title: '选择性别',
    message: h('div', { 
      style: 'padding: 10px; text-align: left;',
      onInput: (e) => {
        selectedGender.value = e.target.value;
      }
    }, [
      h('div', { style: 'margin-bottom: 15px;' }, [
        h('input', {
          type: 'radio',
          name: 'gender',
          value: '男',
          checked: selectedGender.value === '男',
          style: 'margin-right: 8px;',
          onChange: (e) => selectedGender.value = e.target.value
        }),
        h('label', { 
          for: 'gender-male',
          style: 'cursor: pointer; margin-right: 20px;' 
        }, '男')
      ]),
      h('div', { style: 'margin-bottom: 15px;' }, [
        h('input', {
          type: 'radio',
          name: 'gender',
          value: '女',
          checked: selectedGender.value === '女',
          style: 'margin-right: 8px;',
          onChange: (e) => selectedGender.value = e.target.value
        }),
        h('label', { 
          for: 'gender-female',
          style: 'cursor: pointer; margin-right: 20px;' 
        }, '女')
      ])
    ]),
    confirmButtonText: '确认',
    cancelButtonText: '取消',
    showCancelButton: true
  }).then(() => {
    // 点击确认按钮
    // 显示加载提示
    const loadingInstance = showLoadingToast({
      message: '保存中...',
      forbidClick: true,
      duration: 0
    });
    
    // 调用API更新性别
    userStore.updateUserInfo({ gender: selectedGender.value })
      .then((result) => {
        // 关闭加载提示
        loadingInstance.close();
        
        if (result && result.success) {
          showSuccessToast('性别修改成功');
        } else {
          showFailToast((result && result.message) || '性别修改失败');
        }
      })
      .catch((error) => {
        console.error('更新性别失败:', error);
        loadingInstance.close();
        showToast.fail('性别修改失败');
      });
  }).catch(() => {
    // 点击取消按钮
  });
};

const showPhoneDialog = () => {
  // 使用ref创建响应式变量
  const newPhoneValue = ref(userInfo.value?.phone || '');
  
  showDialog({
    title: '修改手机号',
    showCancelButton: true,
    confirmButtonText: '确认',
    className: 'phone-dialog',
    message: h('div', { style: 'text-align: left; padding: 10px 0;' }, [
      h('div', { style: 'margin-bottom: 15px;' }, [
        h('div', { style: 'margin-bottom: 5px; text-align: left;' }, '手机号：'),
        h('input', {
          type: 'tel',
          value: newPhoneValue.value,
          onInput: (e) => { newPhoneValue.value = e.target.value },
          style: 'width: 100%; border: 1px solid #dcdee0; border-radius: 4px; padding: 8px; box-sizing: border-box;'
        })
      ])
    ])
  }).then(async () => {
    // 点击确认按钮
    try {
      // 显示加载提示
      const loadingInstance = showLoadingToast({
        message: '保存中...',
        forbidClick: true,
        duration: 0
      });
      
      console.log('更新手机号:', newPhoneValue.value);
      
      // 调用API更新手机号
      const result = await userStore.updateUserInfo({ phone: newPhoneValue.value });
      
      // 关闭加载提示
      loadingInstance.close();
      
      if (result && result.success) {
        showSuccessToast('手机号修改成功');
      } else {
        showFailToast((result && result.message) || '手机号修改失败');
      }
    } catch (error) {
      console.error('更新手机号失败:', error);
      showToast.clear();
      showToast.fail('手机号修改失败');
    }
  }).catch(() => {
    // 点击取消按钮
  });
};

const showAvatarDialog = () => {
  // 使用ref创建响应式变量
  const selectedFile = ref(null);
  const previewUrl = ref(userInfo.value?.avatar ? `http://192.168.0.114:8000/avatar/${userInfo.value.avatar}` : 'https://fastly.jsdelivr.net/npm/@vant/assets/cat.jpeg');
  
  showDialog({
    title: '修改头像',
    showCancelButton: true,
    confirmButtonText: '确认上传',
    className: 'avatar-dialog',
    message: h('div', { style: 'text-align: left; padding: 10px 0;' }, [
      h('div', { style: 'margin-bottom: 15px; text-align: center;' }, [
        h('van-image', {
          props: {
            round: true,
            width: 100,
            height: 100,
            src: previewUrl.value
          },
          style: 'margin-bottom: 10px;'
        })
      ]),
      h('div', { style: 'margin-bottom: 15px;' }, [
        h('input', {
          type: 'file',
          accept: 'image/*',
          onInput: (e) => {
            const file = e.target.files[0];
            if (file) {
              selectedFile.value = file;
              // 生成预览URL
              previewUrl.value = URL.createObjectURL(file);
            }
          },
          style: 'width: 100%; padding: 8px; box-sizing: border-box; cursor: pointer;'
        })
      ]),
      h('div', { style: 'margin-bottom: 15px; font-size: 12px; color: #999;' }, '请选择本地图片文件，建议使用正方形图片')
    ])
  }).then(async () => {
    // 点击确认按钮
    if (!selectedFile.value) {
      showToast('请选择要上传的图片');
      return;
    }
    
    try {
      // 显示加载提示
      const loadingInstance = showLoadingToast({
        message: '上传中...',
        forbidClick: true,
        duration: 0
      });
      
      // 创建FormData对象
      const formData = new FormData();
      formData.append('avatar_file', selectedFile.value);
      
      // 发送上传请求
      const response = await axios.post(`${apiConfig.baseURL}/api/user/upload-avatar`, formData, {
        headers: {
          'Authorization': `Bearer ${userStore.token}`,
          'Content-Type': 'multipart/form-data'
        }
      });
      
      // 关闭加载提示
      loadingInstance.close();
      
      if (response.data && response.data.success) {
        // 更新用户信息
        await userStore.getUserInfoDetail();
        showSuccessToast('头像上传成功');
      } else {
        showFailToast((response.data && response.data.message) || '头像上传失败');
      }
    } catch (error) {
      console.error('上传头像失败:', error);
      showToast.clear();
      showToast.fail('头像上传失败');
    }
  }).catch(() => {
    // 点击取消按钮
  });
};
</script>

<style scoped>
.profile-page {
  min-height: 100vh;
  background-color: #f7f8fa;
}

.profile-container {
  padding-top: 56px;
  padding-bottom: 20px;
}

.avatar-group,
.info-group,
.security-group {
  margin-top: 12px;
}

.password-dialog .van-dialog__content {
  padding: 20px;
}

.password-form .form-item {
  margin-bottom: 15px;
  text-align: left;
}

.password-form .form-item span {
  display: block;
  margin-bottom: 5px;
  text-align: left;
}

.password-form .password-input {
  width: 100%;
  border: 1px solid #dcdee0;
  border-radius: 4px;
  padding: 8px;
  outline: none;
  box-sizing: border-box;
}
</style>